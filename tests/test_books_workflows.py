from datetime import date, timedelta
from uuid import UUID, uuid4
from io import BytesIO
import zipfile

from app.models.books import Job, Notification, SupportRecord
from app.models.common import utc_now
from app.services.books import catalog_id
from app.services.files import process_one
from app.services.notifications import schedule_reminders
from tests.test_books import (books, headers, post_tx, vehicle, election, uploaded_receipt,
    ActualControlledOCR,CleanScanner,uploaded_statement,CSV,tx_data)


def test_reference_sources_onboarding_vehicle_corrections_and_mileage_edits(client,books):
    auth,business=books
    reference=client.get('/api/v1/reference-data').json()
    assert {x['code'] for x in reference['languages']}=={'en','ur','pa','pl','ro','bn','ar'}
    assert client.put('/api/v1/me/income-sources',headers=headers(auth),json={'source_ids':[str(catalog_id('source','bolt'))]}).status_code==200
    assert client.get('/api/v1/me/income-sources',headers=auth).json()[0]['code']=='bolt'
    row=vehicle(client,auth)
    corrected=client.patch('/api/v1/vehicles/'+row['id'],headers=headers(auth),json={'expected_version':1,'make':'Actual entered make'})
    assert corrected.status_code==200,corrected.text
    row=corrected.json()
    assert election(client,auth,row).status_code==200
    assert client.get('/api/v1/vehicles',headers=auth).json()['items'][0]['make']=='Actual entered make'
    assert client.get('/api/v1/vehicles/'+row['id'],headers=auth).json()['business_miles']=='0.00'
    assert client.patch('/api/v1/vehicles/'+row['id'],headers=headers(auth),json={'expected_version':3,'licence_class':'hackney'}).status_code==409
    assert client.get('/api/v1/me/driver-profile',headers=auth).json()['primary_business_id']==business
    assert client.get('/api/v1/me/tax-profile?tax_year=2026-27',headers=auth).status_code==200
    result=client.patch('/api/v1/me/onboarding',headers=headers(auth),json={'expected_version':1,'current_step':9,'complete':True})
    assert result.status_code==200,result.text
    assert client.get('/api/v1/me/onboarding',headers=auth).json()['completed_at'] is not None
    assert client.get('/api/v1/me',headers=auth).json()['onboarding_complete']
    mileage={'business_id':business,'vehicle_id':row['id'],'occurred_on':'2026-10-20','business_miles':'100.00',
        'start_odometer':'1000.00','end_odometer':'1100.00','purpose':'Evidenced journeys'}
    result=client.post('/api/v1/mileage-logs',headers=headers(auth),json=mileage)
    assert result.status_code==201,result.text
    log=result.json()
    corrected=client.patch('/api/v1/mileage-logs/'+log['id'],headers=headers(auth),json={'expected_version':1,'business_miles':'90.00','private_miles':'10.00'})
    assert corrected.status_code==200,corrected.text
    assert client.post('/api/v1/mileage-logs',headers=headers(auth),json={**mileage,'occurred_on':'2026-10-21'}).status_code==409
    assert client.delete('/api/v1/mileage-logs/'+log['id'],headers=headers(auth),params={'expected_version':2,'reason':'Wrong odometer evidence'}).status_code==204
    assert client.get('/api/v1/mileage-logs?tax_year=2026-27',headers=auth).json()['summary']['deduction_pence']==0


def test_category_personal_weekly_comparison_and_savings_reports(client,books):
    auth,business=books
    income=post_tx(client,auth,business,amount_pence=1000000)
    expense=post_tx(client,auth,business,kind='expense',category_id=str(catalog_id('category','phone_data')),amount_pence=8000,business_use_percent='50.00')
    excluded=post_tx(client,auth,business,kind='expense',category_id=str(catalog_id('category','fines')),amount_pence=5000)
    weekly=client.get('/api/v1/reports/weekly?start_on=2026-10-19',headers=auth).json()
    assert weekly['total_income_pence']==1000000
    categories=client.get('/api/v1/categories/summary?tax_year=2026-27',headers=auth).json()
    assert categories['total_deductible_pence']==4000
    detail=client.get('/api/v1/categories/'+str(catalog_id('category','phone_data'))+'/transactions?tax_year=2026-27',headers=auth).json()
    assert detail['summary']['deductible_pence']==4000
    personal=client.get('/api/v1/reports/personal?tax_year=2026-27',headers=auth).json()
    assert personal['total_pence']==5000
    comparison=client.get('/api/v1/tax/deduction-comparison?tax_year=2026-27&trading_allowance_eligible=true',headers=auth).json()
    assert comparison['trading_allowance']['expense_deduction_pence']==100000
    assert client.get('/api/v1/tax/rules?tax_year=2026-27&region=scotland',headers=auth).json()['rules']
    assert client.get('/api/v1/tax-pot?tax_year=2026-27',headers=auth).json()['balance_pence']==0


def test_receipt_private_photo_export_and_notifications(client,books,session_factory):
    auth,business=books
    row=uploaded_receipt(client,auth,business)
    process_one(session_factory,scanner=CleanScanner(),ocr=ActualControlledOCR())
    row=client.get('/api/v1/receipts/'+row['id'],headers=auth).json()
    assert client.get('/api/v1/receipts/'+row['id']+'/content',headers=auth).status_code==200
    confirmed=client.post('/api/v1/receipts/'+row['id']+'/confirmations',headers=headers(auth),json={
        'expected_version':row['version'],'category_id':str(catalog_id('category','phone_data')),'claim_status':'personal','business_use_percent':'100.00'})
    assert confirmed.status_code==200,confirmed.text
    export=client.post('/api/v1/exports',headers=headers(auth),json={'tax_year':'2026-27','format':'pdf','include_photos':True})
    assert export.status_code==202,export.text
    id=export.json()['id']
    process_one(session_factory)
    assert client.get('/api/v1/exports/'+id,headers=auth).json()['download_ready']
    archive=client.get('/api/v1/exports/'+id+'/download',headers=auth)
    assert archive.status_code==200,archive.text
    with zipfile.ZipFile(BytesIO(archive.content)) as zip:
        assert 'books.pdf' in zip.namelist()
        assert len(zip.namelist())==2
    notifications=client.get('/api/v1/notifications',headers=auth).json()
    assert notifications['unread_count']==2
    notification=notifications['items'][0]
    assert client.patch('/api/v1/notifications/'+notification['id'],headers=headers(auth),json={'read':True}).status_code==200
    result=client.post('/api/v1/notifications/read-all',headers=headers(auth),json={'through':utc_now().isoformat()})
    assert result.status_code==200,result.text
    assert result.json()['unread_count']==0


def test_preference_aware_reminder_dedup_and_consented_accountant_request(client,books,session_factory):
    auth,business=books
    client.patch('/api/v1/me',headers=headers(auth),json={'expected_version':1,'preferences':{'reminder_deadlines':True}})
    assert schedule_reminders(session_factory,date(2027,1,30))==1
    assert schedule_reminders(session_factory,date(2027,1,30))==0
    assert client.get('/api/v1/deadlines?tax_year=2025-26',headers=auth).json()[0]['due_on']=='2027-01-31'
    client.app.state.settings.accountant_recipients=['verified-test-accountant']
    response=client.post('/api/v1/accountant-requests',headers=headers(auth),json={
        'kind':'filing_question','recipient_reference':'verified-test-accountant','message':'Synthetic question','consent_version':'test-v1'})
    assert response.status_code==201,response.text
    assert response.json()['delivered'] is False
    assert client.get('/api/v1/accountant-requests/'+response.json()['id'],headers=auth).json()['status']=='requested'


def test_statement_overlap_and_exact_import_reversal(client,books,session_factory):
    auth,business=books
    statement=uploaded_statement(client,auth,business,session_factory)
    response=client.post('/api/v1/statements/'+statement['id']+'/imports',headers=headers(auth),json={'expected_version':statement['version'],'acknowledged_warning_codes':[]})
    assert response.status_code==200,response.text
    imported=response.json()['statement']
    assert len(client.get('/api/v1/statements?tax_year=2026-27',headers=auth).json()['items'])==1
    assert client.get('/api/v1/statements/'+statement['id']+'/content',headers=auth).status_code==200
    overlapping=uploaded_statement(client,auth,business,session_factory,CSV.replace(b'payout-1',b'payout-2'))
    assert client.post('/api/v1/statements/'+overlapping['id']+'/imports',headers=headers(auth),json={'expected_version':overlapping['version']}).status_code==409
    reversed=client.post('/api/v1/statements/'+statement['id']+'/reversals',headers=headers(auth),json={
        'expected_version':imported['version'],'mutation_id':imported['mutation_id'],'reason':'Reverse this exact import'})
    assert reversed.status_code==200,reversed.text
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['income_pence']==0


def test_reconciliation_link_existing_record_and_reverse_link(client,books,session_factory):
    auth,business=books
    post_tx(client,auth,business,amount_pence=9000,occurred_on='2026-10-05')
    outside=post_tx(client,auth,business,amount_pence=1000,occurred_on='2026-10-08')
    post_tx(client,auth,business,kind='expense',amount_pence=1000,category_id=str(catalog_id('category','platform_fees')),occurred_on='2026-10-05')
    statement=uploaded_statement(client,auth,business,session_factory)
    client.post('/api/v1/statements/'+statement['id']+'/imports',headers=headers(auth),json={'expected_version':statement['version']})
    issue=client.get('/api/v1/reconciliations?tax_year=2026-27',headers=auth).json()['items'][0]
    response=client.post('/api/v1/reconciliations/'+issue['id']+'/resolutions',headers=headers(auth),json={
        'expected_version':issue['version'],'mode':'link_existing','transaction_ids':[outside['id']]})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['issue']['difference_pence']==0
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['income_pence']==10000
    assert client.post('/api/v1/reconciliations/'+issue['id']+'/reversals',headers=headers(auth),json={
        'expected_version':result['issue']['version'],'resolution_id':result['resolution_id'],'mutation_id':result['mutation_id'],'reason':'Undo exact link'}).status_code==200
    assert client.get('/api/v1/transactions/'+outside['id'],headers=auth).json()['import_origin_key'] is None


def test_invalid_partial_updates_return_validation_and_preserve_records(client,books):
    auth,business=books
    row=vehicle(client,auth)
    for patch in [{'registration':None},{'year':1800},{'ownership':None}]:
        response=client.patch('/api/v1/vehicles/'+row['id'],headers=headers(auth),json={'expected_version':1,**patch})
        assert response.status_code==422,response.text
    created=client.post('/api/v1/mileage-logs',headers=headers(auth),json={'business_id':business,'vehicle_id':row['id'],
        'occurred_on':'2026-10-20','business_miles':'100.00','start_odometer':'1000.00','end_odometer':'1100.00','purpose':'Actual evidence'})
    assert created.status_code==201,created.text
    log=created.json()
    for patch in [{'business_miles':'0.00'},{'purpose':None},{'end_odometer':'1050.00'}]:
        response=client.patch('/api/v1/mileage-logs/'+log['id'],headers=headers(auth),json={'expected_version':1,**patch})
        assert response.status_code==422,response.text
    assert client.get('/api/v1/mileage-logs?tax_year=2026-27',headers=auth).json()['summary']['business_miles']=='100.00'


def test_tax_savings_student_loan_and_marriage_declaration():
    from app.services.tax import calculate
    from fastapi import HTTPException
    import pytest
    base={'region':'england_wales_ni','employments':[]}
    savings=calculate(1300000,{**base,'interest_pence':600000},'2026-27')
    assert savings['savings_tax_pence']==8600
    assert savings['income_tax_pence']==17200
    loan=calculate(3000000,{**base,'student_loan_plan':'plan1'},'2026-27')
    assert loan['student_loan_pence']==27900
    no_marriage=calculate(2000000,base,'2026-27')
    with pytest.raises(HTTPException): calculate(2000000,{**base,'marriage_allowance_status':'recipient'},'2026-27')
    declared=calculate(2000000,{**base,'marriage_allowance_status':'recipient','marriage_allowance_eligible':True},'2026-27')
    assert no_marriage['income_tax_pence']-declared['income_tax_pence']==25200


def test_request_body_bound_and_expired_export(client,books,session_factory,db_session):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.models.books import Export
    auth,business=books
    settings=client.app.state.settings.model_copy(update={'upload_max_bytes':1024})
    with TestClient(create_app(settings,session_factory)) as bounded:
        response=bounded.post('/api/v1/receipts',content=b'x'*70000,headers={'Content-Type':'application/octet-stream'})
        assert response.status_code==413
    export=client.post('/api/v1/exports',headers=headers(auth),json={'tax_year':'2026-27','format':'csv','include_photos':False}).json()
    row=db_session.get(Export,UUID(export['id']))
    row.expires_at=utc_now()-timedelta(seconds=1)
    db_session.commit()
    assert client.get('/api/v1/exports/'+export['id']+'/download',headers=auth).status_code==410


def test_election_history_cannot_be_bypassed_and_unused_method_can_change(client,books):
    auth,business=books
    row=vehicle(client,auth)
    first=election(client,auth,row)
    assert first.status_code==200,first.text
    assert first.json()['method_locked'] is False
    changed=election(client,auth,first.json(),method='actual',effective_from='2026-04-07')
    assert changed.status_code==200,changed.text
    second=vehicle(client,auth,registration='ZX26ABC')
    actual=election(client,auth,second,method='actual',prior_capital_allowances=True)
    assert actual.status_code==200,actual.text
    attempted=election(client,auth,actual.json(),method='mileage',effective_from='2026-04-07',prior_capital_allowances=False)
    assert attempted.status_code==422

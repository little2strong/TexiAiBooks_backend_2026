from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4

import pytest
import struct
import zlib
from sqlalchemy import select

from app.models.books import Receipt, Transaction
from app.services.books import catalog_id
from app.services.files import CanonicalCSVParser, ProcessingFailure, process_one
from app.services.ledger import mileage_deduction
from app.services.tax import calculate


def headers(auth,key=None):
    return {**auth,"Idempotency-Key":str(key or uuid4())}


@pytest.fixture
def books(client,account):
    _,auth=account
    response=client.put('/api/v1/me/driver-profile',headers=headers(auth),json={
        'licence_type':'private_hire','council_code':'manual-test','work_pattern':'full_time'})
    assert response.status_code==200,response.text
    business=response.json()['primary_business_id']
    response=client.put('/api/v1/me/tax-profile',headers=headers(auth),json={
        'tax_year':'2026-27','region':'england_wales_ni','has_paye_job':False,'employments':[]})
    assert response.status_code==200,response.text
    return auth,business


def tx_data(business,**changes):
    return {'kind':'income','amount_pence':25000,'occurred_on':'2026-10-20',
        'business_id':business,'source_id':str(catalog_id('source','uber')),**changes}


def post_tx(client,auth,business,**changes):
    response=client.post('/api/v1/transactions',headers=headers(auth),json=tx_data(business,**changes))
    assert response.status_code==201,response.text
    return response.json()


def test_profile_onboarding_bootstrap_and_versions(client,account):
    user,auth=account
    assert client.get('/api/v1/me',headers=auth).json()['first_name'] is None
    key=uuid4()
    data={'first_name':'Synthetic','preferences':{'locale':'bn'},'expected_version':1}
    first=client.patch('/api/v1/me',headers=headers(auth,key),json=data)
    assert first.status_code==200,first.text
    assert first.json()['preferences']['timezone']=='Europe/London'
    assert client.patch('/api/v1/me',headers=headers(auth,key),json=data).json()==first.json()
    assert client.patch('/api/v1/me',headers=headers(auth),json=data).status_code==409
    assert client.patch('/api/v1/me',headers=headers(auth,key),json={**data,'first_name':'Changed'}).status_code==409
    assert client.patch('/api/v1/me/onboarding',headers=headers(auth),json={'expected_version':1,'complete':True}).status_code==409


def test_atomic_ledger_idempotency_corrections_void_and_exact_reverse(client,books):
    auth,business=books
    key=uuid4()
    payload=tx_data(business)
    first=client.post('/api/v1/transactions',headers=headers(auth,key),json=payload)
    assert first.status_code==201,first.text
    row=first.json()
    assert client.post('/api/v1/transactions',headers=headers(auth,key),json=payload).json()==row
    assert client.post('/api/v1/transactions',headers=headers(auth,key),json={**payload,'amount_pence':26000}).status_code==409
    correction=client.patch('/api/v1/transactions/'+row['id'],headers=headers(auth),json={'expected_version':1,'amount_pence':30000})
    assert correction.status_code==200,correction.text
    current=correction.json()
    assert client.patch('/api/v1/transactions/'+row['id'],headers=headers(auth),json={'expected_version':1,'amount_pence':40000}).status_code==409
    assert client.post('/api/v1/transactions/'+row['id']+'/reversals',headers=headers(auth),json={
        'expected_version':2,'mutation_id':row['mutation_id'],'reason':'Wrong earlier action'}).status_code==409
    reverted=client.post('/api/v1/transactions/'+row['id']+'/reversals',headers=headers(auth),json={
        'expected_version':2,'mutation_id':current['mutation_id'],'reason':'Correct this exact edit'})
    assert reverted.status_code==200,reverted.text
    assert reverted.json()['amount_pence']==25000
    assert client.delete('/api/v1/transactions/'+row['id'],headers=headers(auth),params={'expected_version':3,'reason':'Void duplicate'}).status_code==204
    record=client.get('/api/v1/transactions/'+row['id'],headers=auth).json()
    assert record['review_status']=='reversed'
    restored=client.post('/api/v1/transactions/'+row['id']+'/reversals',headers=headers(auth),json={
        'expected_version':4,'mutation_id':record['mutation_id'],'reason':'Restore void'})
    assert restored.status_code==200,restored.text
    assert restored.json()['review_status']=='confirmed'


def test_legacy_expenses_use_same_ledger(client,books,expense_data):
    auth,business=books
    response=client.post('/api/v1/expenses',headers=auth,json={**expense_data,'category':'parking'})
    assert response.status_code==201,response.text
    row=response.json()
    ledger=client.get('/api/v1/transactions/'+row['id'],headers=auth).json()
    assert ledger['legacy_expense_id']==row['id']
    assert ledger['deductible_pence']==1250
    dashboard=client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()
    assert dashboard['deductible_expenses_pence']==1250
    client.patch('/api/v1/expenses/'+row['id'],headers=auth,json={'amount_pence':1500})
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['deductible_expenses_pence']==1500
    client.delete('/api/v1/expenses/'+row['id'],headers=auth)
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['deductible_expenses_pence']==0


def test_ownership_and_bound_cursor_filters(client,books):
    auth,business=books
    rows=[post_tx(client,auth,business,amount_pence=100+i) for i in range(3)]
    first=client.get('/api/v1/transactions?limit=1',headers=auth).json()
    assert first['has_more']
    second=client.get('/api/v1/transactions',params={'limit':1,'cursor':first['next_cursor']},headers=auth).json()
    assert first['items'][0]['id']!=second['items'][0]['id']
    assert client.get('/api/v1/transactions',params={'kind':'expense','cursor':first['next_cursor']},headers=auth).status_code==422
    client.post('/api/v1/auth/register',json={'email':'second@example.com','password':'safe-password-123'})
    other=client.post('/api/v1/auth/login',data={'username':'second@example.com','password':'safe-password-123'}).json()
    other_auth={'Authorization':'Bearer '+other['access_token']}
    assert client.get('/api/v1/transactions/'+rows[0]['id'],headers=other_auth).status_code==404
    assert client.post('/api/v1/transactions',headers=headers(other_auth),json=tx_data(business)).status_code==404
    assert client.get('/api/v1/transactions',params={'cursor':first['next_cursor']},headers=other_auth).status_code==422


def vehicle(client,auth,**changes):
    response=client.post('/api/v1/vehicles',headers=headers(auth),json={
        'registration':'AB26XYZ','ownership':'owned','licence_class':'private_hire','business_start_on':'2026-04-06',**changes})
    assert response.status_code==201,response.text
    return response.json()


def election(client,auth,row,**changes):
    return client.post('/api/v1/vehicles/'+row['id']+'/claim-method',headers=headers(auth),json={
        'expected_version':row['version'],'method':'mileage','effective_from':'2026-04-06',
        'prior_capital_allowances':False,'prior_vehicle_expense_claim':False,'acknowledgement_version':'hmrc-2026-10-27',**changes})


def test_vehicle_eligibility_mileage_bands_corrections_and_cost_exclusion(client,books):
    auth,business=books
    hackney=vehicle(client,auth,registration='CAB26XYZ',licence_class='hackney')
    assert election(client,auth,hackney).status_code==422
    row=vehicle(client,auth)
    elected=election(client,auth,row)
    assert elected.status_code==200,elected.text
    assert elected.json()['method_locked'] is False
    for miles,day in [('9999.00','2026-10-19'),('2.00','2026-10-20')]:
        response=client.post('/api/v1/mileage-logs',headers=headers(auth),json={
            'business_id':business,'vehicle_id':row['id'],'occurred_on':day,'business_miles':miles,'purpose':'Documented test journeys'})
        assert response.status_code==201,response.text
    summary=client.get('/api/v1/mileage-logs?tax_year=2026-27',headers=auth).json()['summary']
    assert summary['deduction_pence']==550025
    current=client.get('/api/v1/vehicles/'+row['id'],headers=auth).json()
    assert current['method_locked']
    assert election(client,auth,current,method='actual').status_code==409
    fuel=post_tx(client,auth,business,kind='expense',category_id=str(catalog_id('category','fuel')),vehicle_id=row['id'])
    assert fuel['deductible_pence']==0
    assert 'covered_by_mileage' in fuel['eligibility_reason_codes']


def test_tax_bands_paye_allowance_and_region():
    base={'region':'england_wales_ni','employments':[]}
    assert calculate(1257000,base,'2026-27')['total_pence']==0
    calc=calculate(2000000,base,'2026-27')
    assert calc['income_tax_pence']==148600
    assert calc['class4_pence']==44580
    combined=calculate(2000000,{**base,'employments':[{'gross_annual_pay_pence':4000000,'tax_paid_pence':548600}]},'2026-27')
    assert combined['income_tax_pence']>calc['income_tax_pence']
    assert calculate(12514000,base,'2026-27')['personal_allowance_pence']==0
    assert calculate(3000000,{**base,'region':'scotland'},'2026-27')['income_tax_pence']!=calculate(3000000,base,'2026-27')['income_tax_pence']
    assert mileage_deduction(Decimal('10001'),'2026-27')==550025
    assert mileage_deduction(Decimal('10001'),'2025-26')==450025


class CleanScanner:
    def scan(self,content): pass


class ActualControlledOCR:
    def extract(self,content,mime):
        return {'merchant':'Controlled extraction','occurred_on':'2026-10-20','amount_pence':5200,'vat_pence':0,'confidence':'0.91','warnings':[]}


def uploaded_receipt(client,auth,business):
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    image=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff'))+chunk(b'IEND',b'')
    response=client.post('/api/v1/receipts',headers=headers(auth),data={'business_id':business},
        files={'file':('receipt.png',image,'image/png')})
    assert response.status_code==202,response.text
    return response.json()['receipt']


def test_receipt_manual_review_atomic_confirmation_exact_reversal(client,books,session_factory):
    auth,business=books
    receipt=uploaded_receipt(client,auth,business)
    assert process_one(session_factory,scanner=CleanScanner(),ocr=ActualControlledOCR())
    row=client.get('/api/v1/receipts/'+receipt['id'],headers=auth).json()
    assert row['processing_status']=='ready'
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['deductible_expenses_pence']==0
    edited=client.patch('/api/v1/receipts/'+row['id'],headers=headers(auth),json={
        'expected_version':row['version'],'merchant':'Reviewed supplier','amount_pence':8000,'occurred_on':'2026-10-21'})
    assert edited.status_code==200,edited.text
    row=edited.json()
    key=uuid4()
    data={'expected_version':row['version'],'category_id':str(catalog_id('category','phone_data')),
        'claim_status':'claimable','business_use_percent':'75.00'}
    confirmed=client.post('/api/v1/receipts/'+row['id']+'/confirmations',headers=headers(auth,key),json=data)
    assert confirmed.status_code==200,confirmed.text
    result=confirmed.json()
    assert result['transaction']['amount_pence']==8000
    assert result['transaction']['deductible_pence']==6000
    assert result['transaction']['description']=='Reviewed supplier'
    assert result['dashboard']['deductible_expenses_pence']==6000
    assert client.post('/api/v1/receipts/'+row['id']+'/confirmations',headers=headers(auth,key),json=data).json()==result
    assert client.post('/api/v1/receipts/'+row['id']+'/confirmations',headers=headers(auth),json={**data,'expected_version':result['receipt']['version']}).status_code==409
    reversed=client.post('/api/v1/receipts/'+row['id']+'/reversals',headers=headers(auth),json={
        'expected_version':result['receipt']['version'],'mutation_id':result['mutation_id'],'reason':'Correct this receipt'})
    assert reversed.status_code==200,reversed.text
    assert reversed.json()['dashboard']['deductible_expenses_pence']==0
    assert client.get('/api/v1/receipts?tax_year=2026-27',headers=auth).json()['counts']['counted']==0


def test_failed_ocr_is_not_success_and_can_retry(client,books,session_factory):
    auth,business=books
    row=uploaded_receipt(client,auth,business)
    process_one(session_factory)
    row=client.get('/api/v1/receipts/'+row['id'],headers=auth).json()
    assert row['processing_status']=='failed'
    assert row['job']['error_code']=='scanner_not_configured'
    assert client.get('/api/v1/receipts/'+row['id']+'/content',headers=auth).status_code==409
    retry=client.post('/api/v1/receipts/'+row['id']+'/ocr-retries',headers=headers(auth),json={'expected_version':row['version']})
    assert retry.status_code==202,retry.text


CSV=b'period_start,period_end,occurred_on,gross_pence,fee_pence,net_pence,adjustment_pence,external_id\n2026-10-01,2026-10-07,2026-10-05,10000,1000,9000,0,payout-1\n'


def uploaded_statement(client,auth,business,session_factory,content=CSV):
    response=client.post('/api/v1/statements',headers=headers(auth),data={
        'business_id':business,'source_id':str(catalog_id('source','uber'))},files={'file':('statement.csv',content,'text/csv')})
    assert response.status_code==202,response.text
    id=response.json()['statement']['id']
    process_one(session_factory,scanner=CleanScanner())
    row=client.get('/api/v1/statements/'+id,headers=auth).json()
    assert row['processing_status']=='ready',row
    return row


def test_statement_gross_fee_net_dedup_and_preview_import(client,books,session_factory):
    auth,business=books
    row=uploaded_statement(client,auth,business,session_factory)
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['income_pence']==0
    key=uuid4()
    data={'expected_version':row['version'],'acknowledged_warning_codes':[]}
    result=client.post('/api/v1/statements/'+row['id']+'/imports',headers=headers(auth,key),json=data)
    assert result.status_code==200,result.text
    assert len(result.json()['transactions'])==2
    dashboard=client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()
    assert dashboard['income_pence']==10000
    assert dashboard['deductible_expenses_pence']==1000
    assert dashboard['profit_pence']==9000
    assert client.post('/api/v1/statements/'+row['id']+'/imports',headers=headers(auth,key),json=data).json()==result.json()
    bad=CSV.replace(b'9000',b'9001')
    with pytest.raises(ProcessingFailure): CanonicalCSVParser().parse(bad,'text/csv')


def test_reconciliation_requires_actual_accounting_and_reverses_exact_effects(client,books,session_factory):
    auth,business=books
    original=post_tx(client,auth,business,amount_pence=9000,occurred_on='2026-10-05')
    statement=uploaded_statement(client,auth,business,session_factory)
    result=client.post('/api/v1/statements/'+statement['id']+'/imports',headers=headers(auth),json={'expected_version':statement['version'],'acknowledged_warning_codes':[]})
    assert result.status_code==200,result.text
    issue=client.get('/api/v1/reconciliations?tax_year=2026-27',headers=auth).json()['items'][0]
    data={'expected_version':issue['version'],'mode':'add_missing','new_transactions':[
        tx_data(business,amount_pence=1000,occurred_on='2026-10-05'),
        tx_data(business,kind='expense',amount_pence=1000,category_id=str(catalog_id('category','platform_fees')),occurred_on='2026-10-05')]}
    resolved=client.post('/api/v1/reconciliations/'+issue['id']+'/resolutions',headers=headers(auth),json=data)
    assert resolved.status_code==200,resolved.text
    row=resolved.json()
    assert row['issue']['difference_pence']==0
    assert row['issue']['fee_difference_pence']==0
    assert client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()['income_pence']==10000
    reverse=client.post('/api/v1/reconciliations/'+issue['id']+'/reversals',headers=headers(auth),json={
        'expected_version':row['issue']['version'],'resolution_id':row['resolution_id'],'mutation_id':row['mutation_id'],'reason':'Undo this resolution'})
    assert reverse.status_code==200,reverse.text
    dashboard=client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()
    assert dashboard['income_pence']==9000
    assert dashboard['deductible_expenses_pence']==0


def test_export_jobs_and_savings_reversal(client,books,session_factory):
    auth,business=books
    post_tx(client,auth,business,description='=MALICIOUS()')
    response=client.post('/api/v1/exports',headers=headers(auth),json={'tax_year':'2026-27','format':'csv','include_photos':False})
    assert response.status_code==202,response.text
    id=response.json()['id']
    assert client.get('/api/v1/exports/'+id+'/download',headers=auth).status_code==409
    process_one(session_factory)
    content=client.get('/api/v1/exports/'+id+'/download',headers=auth)
    assert content.status_code==200,content.text
    assert "'=MALICIOUS()" in content.text
    entry=client.post('/api/v1/tax-pot/entries',headers=headers(auth),json={'amount_pence':2500,'occurred_on':'2026-10-20'}).json()['entry']
    reversed=client.post('/api/v1/tax-pot/entries/'+entry['id']+'/reversals',headers=headers(auth),json={
        'expected_version':1,'mutation_id':entry['mutation_id'],'reason':'Undo savings log'})
    assert reversed.status_code==200,reversed.text
    assert reversed.json()['summary']['balance_pence']==0
    assert reversed.json()['summary']['is_bank_transfer'] is False

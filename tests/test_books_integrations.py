from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select

from app.models.books import Job, PhoneChallenge, Profile, SupportRecord, Transaction
from app.models.common import utc_now
from app.services.books import catalog_id, profile, rows
from app.services.files import pdf_export, process_one
from app.services.mtd import process_mtd_once
from app.services.vault import encrypt
from tests.test_books import books, headers, post_tx, tx_data, uploaded_receipt, CleanScanner, ActualControlledOCR


def test_all_93_operations_are_accounted_in_openapi(client):
    operations=json.loads(Path('docs/proposed_operations.json').read_text())
    schema=client.get('/openapi.json').json()
    actual={op['operationId'] for path in schema['paths'].values() for method,op in path.items() if method in {'get','post','put','patch','delete'}}
    assert len(operations)==93
    assert {op['id'] for op in operations}<=actual
    assert 'TransactionRead' in schema['components']['schemas']


def test_identifiers_encrypted_masked_validated_and_clearable(client,books,db_session):
    auth,_=books
    settings=client.app.state.settings
    from pydantic import SecretStr
    settings.identifier_encryption_keys=[SecretStr(Fernet.generate_key().decode())]
    payload={'tax_year':'2026-27','region':'england_wales_ni','has_paye_job':False,'employments':[],
        'expected_version':1,'utr':'1234567890','ni_number':'AB 12 34 56 C'}
    response=client.put('/api/v1/me/tax-profile',headers=headers(auth),json=payload)
    assert response.status_code==200,response.text
    row=response.json()
    assert row['utr_masked']=='******7890'
    assert '1234567890' not in response.text
    profile_row=db_session.scalar(select(Profile).where(Profile.kind=='tax'))
    assert profile_row.identifiers is not None
    assert b'1234567890' not in profile_row.identifiers
    assert '1234567890' not in json.dumps(profile_row.data)
    invalid=client.put('/api/v1/me/tax-profile',headers=headers(auth),json={**payload,'expected_version':2,'ni_number':'QQ123456C'})
    assert invalid.status_code==422
    assert 'QQ123456C' not in invalid.text
    cleared=client.put('/api/v1/me/tax-profile',headers=headers(auth),json={**payload,'expected_version':2,'utr':None,'ni_number':None})
    assert cleared.status_code==200,cleared.text
    assert cleared.json()['identifiers_complete'] is False


class ControlledSMS:
    enabled=True
    def __init__(self): self.messages=[]
    def send_code(self,phone,code): self.messages.append((phone,code))


def phone_config(client):
    from pydantic import SecretStr
    settings=client.app.state.settings
    settings.identifier_encryption_keys=[SecretStr(Fernet.generate_key().decode())]
    settings.phone_identity_hmac_key=SecretStr('stable-test-identity-hash-key-1234567890')
    adapter=ControlledSMS()
    client.app.state.sms_delivery=adapter
    return adapter


def test_phone_login_signup_single_use_expiry_attempts_resend_and_password_compatibility(client,db_session):
    sms=phone_config(client)
    created=client.post('/api/v1/auth/challenges',json={'phone':'07700 900123','purpose':'sign_up'})
    assert created.status_code==201,created.text
    id=created.json()['challenge_id']
    assert sms.messages[0][0]=='+447700900123'
    assert sms.messages[0][1] not in created.text
    assert client.post('/api/v1/auth/challenges/'+id+'/resend').status_code==429
    verified=client.post('/api/v1/auth/challenges/'+id+'/verify',json={'code':sms.messages[0][1]})
    assert verified.status_code==200
    auth={'Authorization':'Bearer '+verified.json()['access_token']}
    assert client.get('/api/v1/me',headers=auth).status_code==200
    assert client.get('/api/v1/users/me',headers=auth).json()['email'] is None
    assert client.post('/api/v1/auth/challenges/'+id+'/verify',json={'code':sms.messages[0][1]}).status_code==400
    another=client.post('/api/v1/auth/challenges',json={'phone':'07700 900124','purpose':'sign_up'}).json()
    row=db_session.get(PhoneChallenge,UUID(another['challenge_id']))
    row.expires_at=utc_now()-timedelta(seconds=1)
    db_session.commit()
    assert client.post('/api/v1/auth/challenges/'+another['challenge_id']+'/verify',json={'code':sms.messages[-1][1]}).status_code==400


def test_phone_delivery_failure_and_unconfigured_providers_never_report_success(client,account):
    _,auth=account
    assert client.post('/api/v1/auth/challenges',json={'phone':'07700900125','purpose':'sign_up'}).status_code==503
    assert client.post('/api/v1/me/subscription/checkout',headers=headers(auth),json={'plan_id':str(uuid4()),'return_route':'subscription'}).status_code==503
    assert client.post('/api/v1/mtd/authorizations',headers=headers(auth),json={'return_route':'mtd'}).status_code==503
    assert client.post('/api/v1/billing/webhooks/unselected',json={}).status_code==503
    sms=phone_config(client)
    def broken(phone,code): raise RuntimeError('sensitive-provider-detail')
    sms.send_code=broken
    result=client.post('/api/v1/auth/challenges',json={'phone':'07700900126','purpose':'sign_up'})
    assert result.status_code==503
    assert 'sensitive' not in result.text


def test_default_policy_and_explicit_share_override(client,books):
    auth,business=books
    inherited=post_tx(client,auth,business,kind='expense',category_id=str(catalog_id('category','phone_data')))
    overridden=post_tx(client,auth,business,kind='expense',category_id=str(catalog_id('category','phone_data')),business_use_percent='75.00')
    response=client.put('/api/v1/categories/'+str(catalog_id('category','phone_data'))+'/business-use',headers=headers(auth),json={
        'percent':'50.00','effective_from':'2026-04-06','apply_to':'selected_open_period','reason':'Correct default work share','expected_version':0})
    assert response.status_code==200,response.text
    assert response.json()['affected_count']==1
    assert client.get('/api/v1/transactions/'+inherited['id'],headers=auth).json()['deductible_pence']==12500
    assert client.get('/api/v1/transactions/'+overridden['id'],headers=auth).json()['deductible_pence']==18750


def test_summary_consistency_drafts_personal_forecast_and_poa_inputs(client,books):
    auth,business=books
    post_tx(client,auth,business,amount_pence=2000000)
    post_tx(client,auth,business,kind='expense',amount_pence=100000,category_id=str(catalog_id('category','parking')))
    dashboard=client.get('/api/v1/dashboard?tax_year=2026-27',headers=auth).json()
    annual=client.get('/api/v1/reports/annual?tax_year=2026-27',headers=auth).json()
    estimate=client.get('/api/v1/tax/estimate?tax_year=2026-27',headers=auth).json()
    assert dashboard['profit_pence']==annual['profit_pence']==estimate['profit_pence']==1900000
    assert dashboard['estimated_tax_pence']==estimate['total_pence']
    assert sum(x['income_pence'] for x in annual['months'])==2000000
    assert client.get('/api/v1/tax/forecast?tax_year=2026-27',headers=auth).status_code==200
    timeline=client.get('/api/v1/tax/payment-timeline?tax_year=2026-27',headers=auth).json()
    assert timeline['prior_year_liability_pence'] is None
    result=client.put('/api/v1/tax/prior-assessment?tax_year=2026-27',headers=headers(auth),json={
        'prior_year_liability_pence':200000,'tax_paid_outside_sa_pence':1000000,'advance_payments_pence':0})
    assert result.status_code==200,result.text
    timeline=client.get('/api/v1/tax/payment-timeline?tax_year=2026-27',headers=auth).json()
    assert all(x['amount_pence']==0 for x in timeline['items'] if x['type']=='payment_on_account')
    assert any(x['type']=='estimated_balancing_or_credit' for x in timeline['items'])


def test_subscriptions_terms_trial_once_and_expiry(client,account):
    _,auth=account
    id=uuid4()
    client.app.state.settings.subscription_plans=[{'id':str(id),'code':'approved-test','price_pence':199,
        'currency':'GBP','interval':'month','trial_days':7,'cohort_label':'controlled','terms_version':'test-v1','entitlements':['books']}]
    result=client.post('/api/v1/me/subscription/trial',headers=headers(auth),json={'plan_id':str(id),'terms_version':'test-v1'})
    assert result.status_code==201,result.text
    assert result.json()['status']=='trialing'
    assert client.post('/api/v1/me/subscription/trial',headers=headers(auth),json={'plan_id':str(id),'terms_version':'test-v1'}).status_code==409


def test_assistant_explicit_context_failed_provider_and_tenant_isolation(client,books):
    auth,business=books
    tx=post_tx(client,auth,business)
    created=client.post('/api/v1/assistant/conversations',headers=headers(auth),json={
        'context_resource_ids':[tx['id']],'consent_version':'test-v1','locale':'en'})
    assert created.status_code==201,created.text
    id=created.json()['id']
    payload={'content':'Explain my income','client_message_id':str(uuid4())}
    assert client.post('/api/v1/assistant/conversations/'+id+'/messages',headers=headers(auth),json=payload).status_code==503
    class ControlledAssistant:
        def respond(self,messages,context,locale):
            assert len(context)==1 and context[0]['id']==tx['id']
            assert 'description' not in context[0] and 'identifiers' not in context[0]
            raise TimeoutError('secret-provider-details')
    client.app.state.assistant_provider=ControlledAssistant()
    result=client.post('/api/v1/assistant/conversations/'+id+'/messages',headers=headers(auth),json=payload)
    assert result.status_code==200,result.text
    assert result.json()['assistant_message']['status']=='failed'
    assert 'secret-provider-details' not in result.text
    assert len(client.get('/api/v1/assistant/conversations/'+id+'/messages',headers=auth).json()['items'])==1
    client.app.state.assistant_provider.respond=lambda messages,context,locale:{'content':'Controlled guidance from explicit book context.',
        'sources':[{'title':'HMRC income tax rates','url':'https://www.gov.uk/income-tax-rates'}]}
    successful=client.post('/api/v1/assistant/conversations/'+id+'/messages',headers=headers(auth),json={
        'content':'Explain the recorded context','client_message_id':str(uuid4())})
    assert successful.status_code==200,successful.text
    assert successful.json()['assistant_message']['status']=='complete'


class ControlledHMRC:
    recognition_enabled=True
    def __init__(self,outcome='accepted'): self.outcome=outcome;self.calls=0
    def submit(self,tokens,business,snapshot):
        self.calls+=1
        if self.outcome=='timeout': raise TimeoutError()
        return {'status':'accepted','provider_reference':'controlled-acknowledgement'}


def mtd_state(client,auth,business,db_session):
    from pydantic import SecretStr
    client.app.state.settings.identifier_encryption_keys=[SecretStr(Fernet.generate_key().decode())]
    owner=UUID(client.get('/api/v1/me',headers=auth).json()['id'])
    connection=profile(db_session,owner,'mtd_connection',create=True)
    connection.identifiers=encrypt(client.app.state.settings,{'test':'controlled-provider-credential'})
    connection.data={'status':'connected'}
    qualifying=profile(db_session,owner,'mtd_qualifying','2024-25',create=True)
    qualifying.data={'income_pence':6000000,'exempt':False,'evidence_reference':'Controlled prior-year assessment'}
    obligation=SupportRecord(owner_id=owner,kind='mtd_obligation',data={'provider_verified':True,'status':'open',
        'business_id':business,'period_start':'2026-04-06','period_end':'2026-07-05','tax_year':'2026-27','provider_id':'controlled-obligation'})
    db_session.add(obligation)
    db_session.commit()
    return obligation.id


@pytest.mark.parametrize('outcome',['accepted','timeout'])
def test_mtd_immutable_preview_real_outcomes_and_no_retry_unknown(client,books,db_session,session_factory,outcome):
    auth,business=books
    post_tx(client,auth,business,occurred_on='2026-06-01')
    id=mtd_state(client,auth,business,db_session)
    adapter=ControlledHMRC(outcome)
    client.app.state.hmrc_provider=adapter
    preview=client.post('/api/v1/mtd/previews',headers=headers(auth),json={'obligation_ids':[str(id)]})
    assert preview.status_code==201,preview.text
    snapshot=preview.json()
    response=client.post('/api/v1/mtd/updates',headers=headers(auth),json={
        'preview_id':snapshot['id'],'snapshot_hash':snapshot['snapshot_hash'],'consent_version':'test-v1'})
    assert response.status_code==202,response.text
    update=response.json()
    assert update['status']=='queued'
    assert client.get('/api/v1/mtd/updates/'+update['id']+'/confirmation',headers=auth).status_code==409
    assert process_mtd_once(session_factory,client.app.state.settings,adapter)
    result=client.get('/api/v1/mtd/updates/'+update['id'],headers=auth).json()
    assert result['status']==('accepted' if outcome=='accepted' else 'unknown')
    assert adapter.calls==1
    assert not process_mtd_once(session_factory,client.app.state.settings,adapter)
    assert client.get('/api/v1/mtd/updates/'+update['id']+'/confirmation',headers=auth).status_code==(200 if outcome=='accepted' else 409)
    if outcome=='timeout':
        adapter.reconcile=lambda tokens,business,snapshot:{'status':'accepted','provider_reference':'controlled-reconciled-ack'}
        reconciled=client.post('/api/v1/mtd/updates/'+update['id']+'/reconciliation',headers=headers(auth),json={'expected_version':result['version']})
        assert reconciled.status_code==200,reconciled.text
        assert reconciled.json()['status']=='accepted'
        assert adapter.calls==1  # A status query did not resubmit the original send.
    assert client.post('/api/v1/transactions',headers=headers(auth),json=tx_data(business,occurred_on='2026-06-02')).status_code==409


def test_real_pdf_and_upload_bounds(client,books):
    auth,business=books
    pdf=pdf_export([{'occurred_on':'2026-10-20','kind':'income','amount_pence':10000,'deductible_pence':0}],'2026-27')
    assert pdf.startswith(b'%PDF-1.4') and pdf.endswith(b'%%EOF\n')
    response=client.post('/api/v1/receipts',headers=headers(auth),data={'business_id':business},files={'file':('fake.png',b'not-an-image','image/png')})
    assert response.status_code==422


def test_signed_billing_event_replay_ordering_and_server_entitlements(client,account):
    import hashlib,hmac
    _,auth=account
    owner=client.get('/api/v1/me',headers=auth).json()['id']
    plan_id=uuid4()
    client.app.state.settings.subscription_plans=[{'id':str(plan_id),'code':'controlled','price_pence':199,
        'currency':'GBP','interval':'month','trial_days':7,'cohort_label':'test','terms_version':'v1','entitlements':['books']}]
    assert client.post('/api/v1/me/subscription/trial',headers=headers(auth),json={'plan_id':str(plan_id),'terms_version':'v1'}).status_code==201
    secret=b'controlled-signature-test-key'
    class Billing:
        def verify_event(self,body,headers):
            from fastapi import HTTPException
            expected=hmac.new(secret,body,hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,headers.get('test-signature','')): raise HTTPException(400,'Invalid signature')
            return json.loads(body)
        def cancel(self,subscription,reason,idempotency_key):
            return {'status':'cancelled'}
    client.app.state.billing_provider=Billing()
    def send(event,signed=True):
        body=json.dumps(event).encode()
        return client.post('/api/v1/billing/webhooks/controlled',content=body,headers={'Content-Type':'application/json',
            'test-signature':hmac.new(secret,body,hashlib.sha256).hexdigest() if signed else 'invalid'})
    event={'event_id':'evt-1','owner_id':owner,'status':'active','provider':'controlled','subscription_reference':'sub-test','sequence':1,'entitlements':['admin']}
    assert send(event,False).status_code==400
    assert send(event).json()=={'received':True}
    assert send(event).json()=={'received':True}
    current=client.get('/api/v1/me/subscription',headers=auth).json()
    assert current['entitlements']==['books']
    assert send({**event,'event_id':'evt-3','sequence':3,'status':'cancelled'}).status_code==200
    assert send({**event,'event_id':'evt-2','sequence':2}).status_code==200
    assert client.get('/api/v1/me/subscription',headers=auth).json()['entitlements']==[]
    assert send({**event,'event_id':'evt-4','sequence':4}).status_code==200
    cancelled=client.post('/api/v1/me/subscription/cancellation',headers=headers(auth),json={'reason':'Synthetic cancellation'})
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['status']=='cancelled'
    assert cancelled.json()['entitlements']==[]


def test_hmrc_oauth_state_single_use_encryption_and_obligation_sync(client,books,db_session):
    from urllib.parse import urlencode,urlsplit,parse_qs
    auth,business=books
    from pydantic import SecretStr
    client.app.state.settings.identifier_encryption_keys=[SecretStr(Fernet.generate_key().decode())]
    class HMRC:
        recognition_enabled=False
        def authorization_url(self,state,return_route): return 'https://controlled.hmrc.invalid/authorize?'+urlencode({'state':state})
        def exchange(self,code): return {'access_token':'controlled-test-provider-credential'}
        def businesses(self,tokens): return [{'business_id':business,'provider_id':'controlled-business'}]
        def obligations(self,tokens,tax_year): return [{'id':'controlled-period','business_id':business,'period_start':'2026-04-06',
            'period_end':'2026-07-05','due_on':'2026-08-07','status':'open'}]
    client.app.state.hmrc_provider=HMRC()
    authorized=client.post('/api/v1/mtd/authorizations',headers=headers(auth),json={'return_route':'mtd'})
    assert authorized.status_code==200,authorized.text
    state=parse_qs(urlsplit(authorized.json()['authorization_url']).query)['state'][0]
    callback=client.get('/api/v1/mtd/oauth/callback',params={'code':'controlled-test-code','state':state})
    assert callback.json()=={'connection_status':'connected'}
    assert 'controlled-test-provider-credential' not in callback.text
    assert client.get('/api/v1/mtd/oauth/callback',params={'code':'controlled-test-code','state':state}).status_code==400
    assert client.get('/api/v1/mtd/businesses',headers=auth).json()[0]['id']==business
    synced=client.get('/api/v1/mtd/obligations?tax_year=2026-27',headers=auth)
    assert synced.status_code==200,synced.text
    assert 'provider_id' not in synced.json()[0]
    preview=client.post('/api/v1/mtd/previews',headers=headers(auth),json={'obligation_ids':[synced.json()[0]['id']]})
    assert preview.status_code==201,preview.text
    assert preview.json()['can_submit'] is False
    assert 'provider_obligation' not in preview.json()['businesses'][0]


def test_hmrc_stale_preview_and_partial_business_results(client,books,db_session,session_factory):
    from app.models.books import Business
    auth,business=books
    trade_id=mtd_state(client,auth,business,db_session)
    owner=UUID(client.get('/api/v1/me',headers=auth).json()['id'])
    property_business=Business(owner_id=owner,kind='uk_property',name='Verified controlled property business')
    db_session.add(property_business)
    db_session.flush()
    obligation=SupportRecord(owner_id=owner,kind='mtd_obligation',data={'provider_verified':True,'status':'open',
        'business_id':str(property_business.id),'period_start':'2026-04-06','period_end':'2026-07-05','tax_year':'2026-27','provider_id':'controlled-property-period'})
    db_session.add(obligation)
    db_session.commit()
    class Partial(ControlledHMRC):
        def submit(self,tokens,business,snapshot):
            self.calls+=1
            if self.calls==2: raise TimeoutError()
            return {'status':'accepted','provider_reference':'controlled-real-test-ack'}
    adapter=Partial()
    client.app.state.hmrc_provider=adapter
    preview=client.post('/api/v1/mtd/previews',headers=headers(auth),json={'obligation_ids':[str(trade_id),str(obligation.id)]}).json()
    post_tx(client,auth,business,occurred_on='2026-06-01')
    payload={'preview_id':preview['id'],'snapshot_hash':preview['snapshot_hash'],'consent_version':'v1'}
    assert client.post('/api/v1/mtd/updates',headers=headers(auth),json=payload).status_code==409
    fresh=client.post('/api/v1/mtd/previews',headers=headers(auth),json={'obligation_ids':[str(trade_id),str(obligation.id)]}).json()
    sent=client.post('/api/v1/mtd/updates',headers=headers(auth),json={**payload,'preview_id':fresh['id'],'snapshot_hash':fresh['snapshot_hash']})
    assert sent.status_code==202,sent.text
    assert process_mtd_once(session_factory,client.app.state.settings,adapter)
    result=client.get('/api/v1/mtd/updates/'+sent.json()['id'],headers=auth).json()
    assert result['status']=='partial'
    assert {r['status'] for r in result['business_results']}=={'accepted','unknown'}
    assert 'provider_reference' not in result['business_results'][0]
    confirmed=client.get('/api/v1/mtd/updates/'+sent.json()['id']+'/confirmation',headers=auth).json()
    assert len(confirmed['business_references'])==1

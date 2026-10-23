from sentinel.reasoner import validate_model_response, narrative

def test_invalid_evidence_id_rejected():
    assert validate_model_response({'narrative':'این یک توضیح تحلیلی معتبر است','evidence_ids':['E99']},{'E1'}) is None

def test_valid_evidence_id_accepted():
    r=validate_model_response({'narrative':'در لاگ برنامه یک خطای مشخص دیده می‌شود','evidence_ids':['E1']},{'E1'})
    assert r['mode']=='advisory-llm'

def test_llm_optional(monkeypatch):
    monkeypatch.delenv('SENTINEL_LLM_ENDPOINT',raising=False)
    monkeypatch.delenv('SENTINEL_LLM_API_KEY',raising=False)
    monkeypatch.delenv('SENTINEL_LLM_MODEL',raising=False)
    assert narrative({'evidence':[]})['mode']=='rules-only'

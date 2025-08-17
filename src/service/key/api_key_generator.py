from service.auth_service import AuthService

def create_user_key(user_id:str, ENCRYPTION_KEY:str, SIGNING_KEY:str) -> str:
    auth = AuthService(encryption_key=ENCRYPTION_KEY, signing_key=SIGNING_KEY)
    api_key = auth.generate(user_id)

    print("==============================")
    print("  ✅ API KEY 생성 결과")
    print("------------------------------")
    print(f"User ID  :  {user_id}")
    print(f"API KEY  :  {api_key}")
    print("==============================")
    return api_key
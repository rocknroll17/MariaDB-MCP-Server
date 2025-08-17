from service.auth_service import AuthService

ENCRYPTION_KEY=""
SIGNING_KEY =""
auth = AuthService(encryption_key=ENCRYPTION_KEY, signing_key=SIGNING_KEY)

def create(user_id:str) -> str:
    api_key = auth.generate(user_id)

    print("==============================")
    print("  ✅ API KEY 생성 결과")
    print("------------------------------")
    print(f"User ID  :  {user_id}")
    print(f"API KEY  :  {api_key}")
    print("==============================")

create("")

from fastapi import APIRouter, HTTPException, Depends, status
from app.user.user_schema import User, UserLogin, UserUpdate, UserDeleteRequest
from app.user.user_service import UserService
from app.dependencies import get_user_service
from app.responses.base_response import BaseResponse

user = APIRouter(prefix="/api/user")


@user.post("/login", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def login_user(user_login: UserLogin, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    try:
        user = service.login(user_login)
        return BaseResponse(status="success", data=user, message="Login Success.") 
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@user.post("/register", response_model=BaseResponse[User], status_code=status.HTTP_201_CREATED)
def register_user(user: User, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """회원가입 요청을 처리한다.

    Service의 register_user를 호출해 새 유저를 저장하고, 성공 응답을 반환한다.
    이미 존재하는 이메일이면 Service가 ValueError를 던지며, 이 경우 400을 반환한다.
    """
    try:
        new_user = service.register_user(user)
        return BaseResponse(status="success", data=new_user, message="User registration success.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@user.delete("/delete", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def delete_user(user_delete_request: UserDeleteRequest, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """유저 삭제 요청을 처리한다.

    Service의 delete_user를 호출해 유저를 삭제하고, 삭제된 유저 정보를 반환한다.
    이메일에 해당하는 유저가 없으면 Service가 ValueError를 던지며, 이 경우 404를 반환한다.
    """
    try:
        deleted_user = service.delete_user(user_delete_request.email)
        return BaseResponse(status="success", data=deleted_user, message="User Deletion Success.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@user.put("/update-password", response_model=BaseResponse[User], status_code=status.HTTP_200_OK)
def update_user_password(user_update: UserUpdate, service: UserService = Depends(get_user_service)) -> BaseResponse[User]:
    """비밀번호 변경 요청을 처리한다.

    Service의 update_user_pwd를 호출해 비밀번호를 변경하고, 갱신된 유저 정보를 반환한다.
    이메일에 해당하는 유저가 없으면 Service가 ValueError를 던지며, 이 경우 404를 반환한다.
    """
    try:
        updated_user = service.update_user_pwd(user_update)
        return BaseResponse(status="success", data=updated_user, message="User password update success.")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

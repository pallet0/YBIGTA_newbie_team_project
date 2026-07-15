from app.user.user_repository import UserRepository
from app.user.user_schema import User, UserLogin, UserUpdate

class UserService:
    def __init__(self, userRepoitory: UserRepository) -> None:
        self.repo = userRepoitory

    def login(self, user_login: UserLogin) -> User:
        """입력받은 유저 정보에 대한 로그인을 진행합니다.

        Args:
            user_login (UserLogin): 로그인에 필요한 이메일, 비밀번호를 담은 UserLogin 객체

        Raises:
            ValueError: 해당 이메일의 유저가 존재하지 않을 시
            ValueError: 비밀번호가 일치하지 않을 시

        Returns:
            User: 로그인에 성공한 User 객체
        """
        user = self.repo.get_user_by_email(user_login.email)
        if user is None:
            raise ValueError("User not Found.")
        
        if user.password != user_login.password:
            raise ValueError("Invalid ID/PW")
        
        return user
        
    def register_user(self, new_user: User) -> User:
        """입력받은 유저 정보를 기반으로 새로운 유저를 등록합니다.

        Args:
            new_user (User): 새로운 유저 정보를 담은 User 객체

        Raises:
            ValueError: 해당 이메일의 유저가 이미 존재할 시

        Returns:
            User: 등록에 성공한 User 객체
        """
        if self.repo.get_user_by_email(new_user.email) is not None:
            raise ValueError("User already Exists.")
        
        new_user1 = self.repo.save_user(new_user)
        return new_user1

    def delete_user(self, email: str) -> User:
        """입력받은 유저 이메일에 해당하는 유저를 삭제합니다.

        Args:
            email (str): 삭제할 유저의 이메일

        Raises:
            ValueError: 해당 이메일의 유저가 존재하지 않을 시

        Returns:
            User: 삭제에 성공한 User 객체
        """
        ## TODO        
        user = self.repo.get_user_by_email(email)
        if user is None:
            raise ValueError("User not Found.")
        self.repo.delete_user(user)
        return user

    def update_user_pwd(self, user_update: UserUpdate) -> User:
        """입력받은 유저 이메일에 해당하는 유저의 비밀번호를 업데이트합니다. 

        Args:
            user_update (UserUpdate): 업데이트할 유저 이메일과c 비밀번호가 있는 UserUpdate 객체

        Raises:
            ValueError: 해당 이메일의 유저가 존재하지 않을 시

        Returns:
            User: 업데이트에 성공한 User 객체
        """
        user = self.repo.get_user_by_email(user_update.email)
        if user is None:
            raise ValueError("User not Found.")

        user.password = user_update.new_password
        updated_user = self.repo.save_user(user)
        
        return updated_user
        
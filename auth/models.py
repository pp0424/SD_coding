# 创建简单的用户类
class User:
    def __init__(self, id):
        self.id = id
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
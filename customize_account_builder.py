from datetime import timedelta

class CustomizeAccountBuilder:
    def __init__(self, account):
        self.account = account or {}
        self.result = {}

    def convert_balance_to_hours(self):
        """Converts the balance from HH:MM format to hours."""
        balance = self.account.get('balance', '0:0')  

        
        if isinstance(balance, str):
            try:
                
                hours, minutes = map(int, balance.split(':'))
                balance_minutes = (hours * 60) + minutes  
                balance_hours = balance_minutes / 60  
            except ValueError:
                
                balance_hours = 0.0
        else:
            
            try:
                balance_hours = float(balance)
            except (ValueError, TypeError):
                balance_hours = 0.0

        self.result['balance_hours'] = round(balance_hours, 2)
        return self

    def determine_premium_status(self):
        """Determines if the account is premium based on balance_hours."""
        balance_hours = self.result.get('balance_hours', 0)
        self.result['is_premium'] = balance_hours > 50  
        return self

    def build(self):
        """Assembles the final account dictionary."""
        return {
            'account': {**self.account, 'balance': self.result['balance_hours']},
            'is_premium': self.result['is_premium']
        }

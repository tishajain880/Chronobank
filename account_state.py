class AccountState:
    def get_status(self):
        raise NotImplementedError()

class ActiveState(AccountState):
    def get_status(self):
        return "Active"

class OverdrawnState(AccountState):
    def get_status(self):
        return "Overdrawn"

class FrozenState(AccountState):
    def get_status(self):
        return "Frozen (Fraud Detected)"

class Account:
    def __init__(self, account_number, balance, status_code):
        self.account_number = account_number
        self.balance = balance
        self.state = self._load_state(status_code)

    def _load_state(self, code):
        if code == "active":
            return ActiveState()
        elif code == "overdrawn":
            return OverdrawnState()
        elif code == "frozen":
            return FrozenState()
        else:
            return ActiveState()

    def get_state_description(self):
        return self.state.get_status()

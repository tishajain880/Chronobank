import hashlib
import json
from time import time

class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.create_block(previous_hash='1')

    def create_block(self, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.pending_transactions,
            'previous_hash': previous_hash,
        }
        block['hash'] = self.hash_block(block)
        self.pending_transactions = []
        self.chain.append(block)
        return block

    def add_transaction(self, sender_id, receiver_id, amount, txn_type):
        self.pending_transactions.append({
            'sender': sender_id,
            'receiver': receiver_id,
            'amount': amount,
            'type': txn_type,
            'timestamp': time()
        })
        return self.get_last_block()['index'] + 1

    def get_last_block(self):
        return self.chain[-1]

    def hash_block(self, block):
        block_copy = block.copy()
        block_copy['hash'] = ''
        block_string = json.dumps(block_copy, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]
            if curr['previous_hash'] != prev['hash']:
                return False
            if curr['hash'] != self.hash_block(curr):
                return False
        return True

from eth_account import Account
from eth_account.messages import encode_defunct
from utils.utils import error_handler, check_proxy, get_proxy
from utils.constants import DEFAULT_PRIVATE_KEYS
import requests
from fake_useragent import UserAgent
import json
import brotli
from loguru import logger

class Checker(): 

    def __init__(self,private_key:str, proxy:dict = None): 

        self.account = Account.from_key(private_key)
        self.proxy = proxy 
        self.base_url = 'https://claims.movementnetwork.xyz/api/'
        self.headers = {
            'accept':'*/*',
            'accept-encoding':'gzip, deflate, br, zstd',
            'accept-language':'en-US;q=0.8,en;q=0.7',
            'referer': 'https://claims.movementnetwork.xyz/',
            'user-agent': UserAgent().random
        }

    @error_handler('getting nonce')
    def _get_nonce(self,): 

        url = self.base_url + 'get-nonce'
        response = requests.get(url, proxies=self.proxy,headers=self.headers)
        response_json = json.loads(response.content.decode())
        return response_json['nonce']
    
    @error_handler('getting amount')
    def get_amount(self): 

        nonce = self._get_nonce()
        message = f'Please sign this message to confirm ownership. nonce: {nonce}'

        encoded_msg = encode_defunct(text=message)
        signature = self.account.sign_message(encoded_msg).signature.hex()

        url = self.base_url + 'claim/start'
        self.headers['origin'] = 'https://claims.movementnetwork.xyz'
        payload = {
            'address': self.account.address,
            'message': message,
            'nonce': nonce,
            'signature': signature
        }
        response = requests.post(url, proxies=self.proxy, json=payload, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f'Error getting amount: {response.status_code}')
        
        if not response.json()['isEligible'] : 
            logger.warning(f'{self.account.address} is not eligible for claim')
            return 0
        
        if response.json()['isEligible']: 
            logger.success(f'{self.account.address} is eligible for claim with amount: {response.json()["amount"]}')
            return response.json()['amount']
        

def main(): 

    check_proxy()

    with open(DEFAULT_PRIVATE_KEYS, 'r', encoding='utf-8') as f: 
        private_keys = f.read().splitlines()

    total_amount = 0
    for private_key in private_keys: 
        proxy = get_proxy(private_key)
        checker = Checker(private_key, proxy)
        total_amount += checker.get_amount()
    
    logger.success(f'Total amount to claim: {total_amount}')

if __name__ == '__main__': 
    main()
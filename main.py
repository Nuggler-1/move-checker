from eth_account import Account
from eth_account.messages import encode_defunct
from utils.utils import error_handler, check_proxy, get_proxy, sleep
from utils.constants import DEFAULT_PRIVATE_KEYS, DEFAULT_RESULTS
import requests
from fake_useragent import UserAgent
import json
import questionary
from loguru import logger
import sys
from config import DELAY_ACCOUNTS

logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> |  <level>{message}</level>",
    colorize=True
)
class Checker(): 

    def __init__(self,private_key:str, proxy:dict = None): 

        self._private_key = private_key
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

        self.message = ''
        self.signature = ''

    @error_handler('getting nonce')
    def _get_nonce(self,): 

        url = self.base_url + 'get-nonce'
        response = requests.get(url, proxies=self.proxy,headers=self.headers)
        response_json = json.loads(response.content.decode())
        return response_json['nonce']
    
    @error_handler('getting amount')
    def get_amount(self, ): 

        nonce = self._get_nonce()
        if nonce == 0:
            return 0
        self.message = f'Please sign this message to confirm ownership. nonce: {nonce}'

        encoded_msg = encode_defunct(text=self.message)
        self.signature = self.account.sign_message(encoded_msg).signature.hex()

        url = self.base_url + 'claim/start'
        self.headers['origin'] = 'https://claims.movementnetwork.xyz/'
        payload = {
            'address': self.account.address,
            'message': self.message,
            'nonce': nonce,
            'signature': self.signature
        }
        response = requests.post(url, proxies=self.proxy, json=payload, headers=self.headers)

        if response.status_code != 200:
            raise Exception(f'Error getting amount: {response.status_code}')
        
        if response.json()['claimedOnL1']:
            logger.warning(f'{self.account.address}: already claimed {response.json()['amount']} on L1')
            return 0
        
        if response.json()['claimedOnL2']:
            logger.warning(f'{self.account.address}: already claimed {response.json()['amountL2']} on L2')
            return 0
        
        if response.json()['eligibility_status'] != "eligible": 
            logger.warning(f'{self.account.address}: is not eligible for claim')
            logger.warning(f'{self.account.address}: eligibility status from api: {response.json()["eligibility_status"]}')
            return 0
        
        if response.json()['isEligible']: 
            logger.success(f'{self.account.address}: is eligible for claim with amount: {response.json()["amountL2"]}')
            return int(response.json()['amountL2'])
        
    @error_handler('registering mainnet')
    def register_mainnet(self): 

        amount = self.get_amount()
        if amount == 0: 
            return 0
        
        url = self.base_url + 'claim/l2'

        response = requests.post(
            url, 
            proxies=self.proxy, 
            json={
                'address': self.account.address,
                'message': self.message,
                'signature': self.signature
            }, 
            headers=self.headers
        )

        if response.status_code != 200: 
            raise Exception(f'Error registering mainnet: {response.status_code}: {response.text}')
        
        if response.json()['success']: 
            logger.success(f'{self.account.address}: {response.json()["message"]}')
            self.save_results('success')
            return amount
        else:
            logger.warning(f'{self.account.address}: {response.json()["message"]}')
            return 0

        
    
    @error_handler('save results')
    def save_results(self, message:str, file:str = DEFAULT_RESULTS): 

        with open(file, 'a', encoding='utf-8') as f: 
            f.write(f'{self._private_key}:{message}\n')
        
        return

def main(): 

    check_proxy()

    with open(DEFAULT_PRIVATE_KEYS, 'r', encoding='utf-8') as f: 
        private_keys = f.read().splitlines()

    choice = questionary.select(
            "Select work mode:",
            choices=[
                "Register L2 drop",
                "Check L2 drop",
                "Exit"
            ]
    ).ask()

    match choice:

        case "Register L2 drop":
            f = open(DEFAULT_RESULTS, 'w')
            f.close()
            total_amount = 0
            for private_key in private_keys: 
                proxy = get_proxy(private_key)
                checker = Checker(private_key, proxy)
                registered = checker.register_mainnet()
                if not registered: 
                    logger.warning(f'{checker.account.address}: could not register')
                    checker.save_results('failed')
                    continue
                total_amount += registered
                sleep(DELAY_ACCOUNTS)
            logger.success(f'Total amount registered on L2: {total_amount}')
            
        case "Check L2 drop":
            total_amount = 0
            for private_key in private_keys: 
                proxy = get_proxy(private_key)
                checker = Checker(private_key, proxy)
                amount = checker.get_amount()
                total_amount += amount 
            logger.success(f'Total amount to claim on L2: {total_amount}')

        case "Exit":
            return

if __name__ == '__main__': 
    main()

from web3 import Web3
from config import MAX_TX_WAIT, GAS_MULT, TX_RETRIES
from .utils import error_handler, intToDecimal, decimalToInt
from .constants import ERC20_ABI
from loguru import logger
import time


class AccountEVM: 

    def __init__(self, private_key: str, rpc: str, proxy:dict = None, tx_timeout = MAX_TX_WAIT, eip1559 = True):

        self.private_key = private_key
        self.web3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'proxies': proxy}))
        self.account = self.web3.eth.account.from_key(private_key)
        self.tx_timeout = tx_timeout
        self.eip1559 = eip1559

    @error_handler('check tx')
    def _get_gas_prices(self, tx_dict: dict = None,) -> dict: 
        
        if tx_dict is None:
            tx_dict = {}

        if self.eip1559:
            fee_history = self.web3.eth.fee_history(5, 'latest', [10, 20, 30])

            #average base fee
            base_fees = fee_history['baseFeePerGas']
            avg_base_fee = sum(base_fees) / len(base_fees)

            #average priority fee
            priority_fees = fee_history['reward']
            avg_priority_fee = sum([sum(rewards) / len(rewards) for rewards in priority_fees]) / len(priority_fees)

            max_fee_per_gas = avg_base_fee + avg_priority_fee * GAS_MULT
            max_priority_fee_per_gas = avg_priority_fee

            tx_dict['maxFeePerGas'] = int(max_fee_per_gas)
            tx_dict['maxPriotiyFeePerGas'] = int(max_priority_fee_per_gas)

        else: 
            gas_price = int(self.web3.eth.gas_price * GAS_MULT)
            tx_dict['gasPrice'] = gas_price

        return tx_dict
    
    @error_handler('check tx')
    def _check_transaction(self, hash_tx:str) -> int:

        tx_data = self.web3.eth.wait_for_transaction_receipt(hash_tx, timeout=self.tx_timeout)

        if (tx_data['status'])== 1:
            logger.success(f'Transaction  {Web3.to_hex(tx_data["transactionHash"])}')
            return 1

        elif (tx_data['status'])== 0: 
            logger.warning(f'Transaction failed  {Web3.to_hex(tx_data["transactionHash"])}: {tx_data["logs"]}')
            return 0

    error_handler('gas waiter')
    def wait_for_gas(self, max_gas: float ) -> None: 

        """max_gas: float = max gas price in gwei"""

        while True: 
            
            try: 
                if self.web3.eth.gas_price < Web3.to_wei(max_gas, 'gwei'): 
                    return  
                logger.info(f'Waiting for gas to drop. Current {Web3.from_wei(self.web3.eth.gas_price, "gwei")}')

            except: 
                pass 

            time.sleep(20)

    @error_handler('build_and_send_tx', retries=TX_RETRIES)
    def build_and_send_tx(self, tx, value: int = 0, return_hash: bool = False, custom_gasprice: float = 0) -> int | str:

        """tx = contract method"""
    
        gas = tx.estimate_gas({'value':value, 'from':self.account.address, 'gas': 0})

        gas = int(gas*1.2)

        nonce = self.web3.eth.get_transaction_count(self.account.address)

        tx_dict = {
                    'from':self.account.address,
                    'value':value,
                    'nonce':nonce,
                    'gas':gas,
                }

        tx_dict = self._get_gas_prices(tx_dict)

        built_tx = tx.build_transaction(
                tx_dict
            )

        signed_tx = self.account.sign_transaction(built_tx)
        hash_tx = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f'{self.account.address}: Transaction was sent')
        tx_passed = self._check_transaction(hash_tx)

        if tx_passed == 1:
            if return_hash == False:
                return tx_passed
            else: 
                return hash_tx.hex()
        else: 
            raise Exception('Transaction failed')
    
    
    @error_handler('send tx', retries=TX_RETRIES)
    def send_tx(self, tx_dict:dict, return_hash: bool = False) -> int | str:

        tx_dict['to'] = Web3.to_checksum_address(tx_dict['to'])
        tx_dict['from'] = Web3.to_checksum_address(tx_dict['from'])
        tx_dict['value'] = int(tx_dict['value'])
    
        gas = self.web3.eth.estimate_gas(tx_dict)
        nonce = self.web3.eth.get_transaction_count(self.account.address)

        tx_dict['chainId'] = self.web3.eth.chain_id
        tx_dict['nonce'] = nonce
        tx_dict['gas'] = gas 

        tx_dict = self._get_gas_prices(tx_dict)

        signed_tx = self.account.sign_transaction(tx_dict)
        hash_tx = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f'{self.account.address}: Transaction was sent')
        tx_passed = self._check_transaction( hash_tx)

        if tx_passed == 1:
            if return_hash == False:
                return tx_passed
            else: 
                return hash_tx.hex()
        else: 
            raise Exception('Transaction failed')
        
    @error_handler('approve', retries=TX_RETRIES)    
    def approve(self, approving_token: str, approve_receiver: str, amount:int, approve_max:bool = False): #amount в decimal

        """
        approving_token: str = token address

        approve_receiver: str = address to approve

        amount: int = amount to approve in human readable format

        approve_max: bool = approve max or approve amount 

        """

        contract = self.web3.eth.contract(address = approving_token, abi = ERC20_ABI)

        allowance = contract.functions.allowance(self.account.address, approve_receiver).call()
        decimals = contract.functions.decimals().call()
        amount = intToDecimal(amount, decimals)

        if allowance < amount: 
            logger.info(f'{self.account.address}: Approving tokens')
            
            if approve_max == True: 
                amount = (2 ** 256 - 1)
            
            approve_tx = contract.functions.approve(approve_receiver,amount)
            tx = self.build_and_send_tx(approve_tx)

            return tx
        
        else: 
            logger.info(f'{self.account.address}: Approve not needed')
            return 1
        
    @error_handler('get_erc20_balance')
    def get_erc20_balance(self, token_address:str, fixed_decimal:bool = False, return_decimal:bool = False) -> float | tuple[int,int]: 

        """
        token_address: str = token address 

        returns balance in human readable format or tuple(balance, decimals)
        """

        contract = self.web3.eth.contract(address = token_address, abi = ERC20_ABI)
        decimals = contract.functions.decimals().call()
        balance = contract.functions.balanceOf(self.account.address).call()

        if fixed_decimal == False: 

            balance = decimalToInt(balance,decimals)

        if return_decimal == True:
            return balance, decimals
        else: 
            return balance
            
        
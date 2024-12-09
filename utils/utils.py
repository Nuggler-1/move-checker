
from loguru import logger
from math import ceil
from config import *
from .constants import *
import asyncio
import time
import sys
import random


def intToDecimal(qty, decimal):
    return int(qty * int("".join(["1"] + ["0"]*decimal)))

def decimalToInt(price, decimal):
    return price/ int("".join((["1"]+ ["0"]*decimal)))

def sleep(sleeping):

    sleep_time = random.randrange(sleeping[0], sleeping[1])
    logger.info(f'Waiting {sleep_time} secs')
    time.sleep(sleep_time)


def error_handler(error_msg, retries = ERR_ATTEMPTS):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(0, retries):
                try: 
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"{error_msg}: {str(e)[:100]}")
                    logger.info(f'Retrying in 10 sec. Attempts left: {ERR_ATTEMPTS-i}')
                    time.sleep(10)
                    if i == retries-1: 
                        return 0
        return wrapper
    return decorator

def async_error_handler(error_msg, retries=ERR_ATTEMPTS):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for i in range(0, retries):
                try:
                    return await func(*args, **kwargs)
                
                except TimeoutError as e:
                    logger.error(f"{error_msg}: TimeoutError - {str(e)[:250]}")
                    if i == retries - 1:
                        return 0
                    logger.info(f"TimeoutError: Retrying in 10 sec. Attempts left: {retries-i-1}")
                    await asyncio.sleep(10)

                except Exception as e:
                    logger.error(f"{error_msg}: {str(e)}")
                    if i == retries - 1:
                        return 0
                    logger.info(f"Retrying in 10 sec. Attempts left: {retries-i-1}")
                    await asyncio.sleep(10)
                    
        return wrapper
    return decorator

def pad32Bytes(data):
      s = data[2:]
      while len(s) < 64 :
        s = "0" + s
      return s

def get_proxy(private, privates=DEFAULT_PRIVATE_KEYS): 

    with open(DEFAULT_PROXIES, 'r') as f: 
        proxies = f.read().splitlines()
        if len(proxies) == 0:
            return None
        
    with open(privates, 'r') as f: 
        privates = f.read().splitlines()
            
    n = privates.index(str(private))
    proxy = proxies[n]
    proxy = {
        'http': f'http://{proxy}',
        'https': f'http://{proxy}'
    }
    return proxy

def check_proxy():

    with open(DEFAULT_PROXIES, 'r') as f: 
        proxies = f.read().splitlines()
    with open(DEFAULT_PRIVATE_KEYS, 'r') as f: 
        keys = f.read().splitlines()
        private_keys = []
        for key in keys: 
            private_keys.append(key.split(':')[0])

    if len(proxies) < len(private_keys) and len(proxies) != 0:
        logger.error('Proxies do not match private keys')
        sys.exit()

def split_list_into_chunks(lst, n):
  
  size = ceil(len(lst) / n)

  return list(
    map(lambda x: lst[x * size:x * size + size],
    list(range(n)))
  )

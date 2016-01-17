# -*- coding:utf-8 -*-
import sys 
sys.path.append("../")

from jingtumsdk.jingtumwallet import init_api_server
from jingtumsdk.jingtumwallet import JingtumWallet
from jingtumsdk.websocketclient import WebSocketClient 
from jingtumsdk.entities import Balance 
from jingtumsdk.logger import logger
import config
import threading
import json
import time

# root account just for test
test_address = "jHb9CJAWyB4jr91VRWn96DkukG4bwdtyTh"
test_secret = "snoPBjXtMeMyMHUVTgbuqAfg1SUTb"
test_issuer = "jBciDE8Q3uJjf111VeiUNM775AMKHEbBLS"

# ulimit account just for test
test_ulimit_address = "jJ8PzpT7er3tXEWaUsVTPy3kQUaHVHdxvp"
test_ulimit_secret = "shYK7gZVBzw4m71FFqZh9TWGXLR6Q"

# Step 1: init server info 
init_api_server(config.server_host, config.server_port, config.is_https, config.api_version)

# Step 2: connect websocket
websockethelper = WebSocketClient(config.web_socket_address) 

class JingtumAccount(JingtumWallet):
    def __init__(self, address=None, secret=None):
        #JingtumWallet.__init__(self, address, secret)
        super(JingtumAccount, self).__init__(address, secret)
        self.currency = None
        self.last_resource_id = None
        self.last_order_hash = None

    def set_last_order_hash(self, hash_id):
        self.last_order_hash = hash_id

    def update_currency(self, data):
        self.currency = {}
        for _d in data:
            self.currency[(_d["currency"], _d["counterparty"])] = Balance(**_d)
        logger.info("update currency:" + str(self.currency))

    def get_balances(self, currency=None, counterparty=None):
        _ret_list = []
        try:
            _ret_list = super(JingtumAccount, self).get_balances(currency, counterparty)
        except Exception, e:
            logger.error("get_balances:" + str(e))

        self.update_currency(_ret_list)
        return _ret_list


def do_socket_receive(data, *arg):
    global test_account_status
    
    logger.info("do_socket_receive0")

    if data.has_key("success") and data["success"]:
        if data.has_key("type") and data["type"] == "Payment":
            arg[0][0].get_balances()

            # set currency 
            if arg[0][0].currency.has_key(("USD", test_issuer)):
                test_account_status = 3
            elif arg[0][0].currency.has_key(("SWT", "")):
                test_account_status = 2
        elif data.has_key("type") and data["type"] == "OfferCreate":
            logger.info("offer created:" + str(data) + str(arg))

            # set last order hash for next test
            if data.has_key("transaction"):
                arg[0][0].set_last_order_hash(data["transaction"]["hash"])

            test_account_status = 4
        elif data.has_key("type") and data["type"] == "OfferCancel":
            logger.info("offer canceled:" + str(data) + str(arg))


            # # set last order hash for next test
            # if data.has_key("transaction"):
            #     arg[0][0].set_last_order_hash(data["transaction"]["hash"])

            test_account_status = 7
        else:
            logger.info("do_socket_receive:" + str(data) + str(arg))



if __name__ == '__main__':
    global test_account_status
    test_account_status = 1
    jt_account = None
    jt_test_ulimit_account = JingtumAccount(test_ulimit_address, test_ulimit_secret)
    jt_test_account = JingtumAccount(test_address, test_secret)
    
    # start with create account
    if test_account_status:
        jt_account = JingtumAccount()

        _wallet_dict = jt_account.generate_wallet() 
        print _wallet_dict
        
        jt_test_account.active_account("SWT", 50, jt_account.address)

    else:
        jt_account = JingtumAccount("jfg27BowdBZv6NKnMY94NSpFrzkEWRb1yy", "sporReJYeHrxA5pHC8ShpLhfXu6sL")
        print jt_account.get_balances()

    if jt_account is not None:
        websockethelper.subscribe_message_by_account(jt_account.address, jt_account.secret)
        t = threading.Thread(target=websockethelper.receive, args=(do_socket_receive, jt_account))
        t.setDaemon(True)
        t.start()

    # status check and action
    while 1:
        #try:
            if test_account_status in (0, 1):
                pass
            elif test_account_status == 2:
                if jt_account.last_resource_id is not None:
                    r = jt_account.get_payment(jt_account.last_resource_id)
                    logger.info("get_payment test:" + str(r))

                jt_test_ulimit_account.payment("USD", 2, jt_account.address, test_issuer)
                test_account_status = 0
            elif test_account_status == 3: 
                r = jt_account.get_paths(test_ulimit_address, test_ulimit_secret, jt_account.address, "1.00", "USD", issuer=test_issuer)
                logger.info("get_paths test:" + str(r))
                
                jt_account.place_order("buy", "SWT", 5, "USD", 1, None, test_issuer)
                test_account_status = 0
            elif test_account_status == 4:
                r = jt_account.get_payments(results_per_page=1, page=1)
                logger.info("get_payments test:" + str(r))
                test_account_status = 5
            elif test_account_status == 5:
                r = jt_account.get_account_orders()
                logger.info("get_account_orders test:" + str(r))
                test_account_status = 6
            elif test_account_status == 6:
                r = jt_account.cancel_order(1)
                logger.info("cancel_order 1 test:" + str(r))
                test_account_status = 0
            elif test_account_status == 7:
                #print "last_hash_id", jt_account.last_order_hash
                if jt_account.last_order_hash is not None:
                    r = jt_account.get_order_by_hash(jt_account.last_order_hash)
                    logger.info("get_order_by_hash test:" + str(r))
                test_account_status = 8
            elif test_account_status == 8:
                base = "USD+" + test_issuer
                counter = "SWT" 
                r = jt_account.get_order_book(base, counter)
                logger.info("get_order_book test:" + str(r.keys()))
                test_account_status = 9
            elif test_account_status == 9:
                if jt_account.last_order_hash is not None:
                    r = jt_account.retrieve_order_transaction(jt_account.last_order_hash)
                    logger.info("retrieve_order_transaction test:" + str(r))
                test_account_status = 10
            elif test_account_status == 10:
                r = jt_account.order_transaction_history()
                logger.info("order_transaction_history test:" + str(r))
                test_account_status = 11
            elif test_account_status == 11:
                if jt_account.last_order_hash is not None:
                    r = jt_account.get_notification(jt_account.last_order_hash)
                    logger.info("get_notification test:" + str(r))
                test_account_status = 12
            elif test_account_status == 12:
                if jt_account.last_order_hash is not None:
                    r = jt_account.get_connection_status()
                    logger.info("get_connection_status test:" + str(r))
                test_account_status = 13
            elif test_account_status == 13:
                r = jt_account.add_relations("authorize", test_address,
                    limit_currency="USD", limit_issuer=test_issuer, limit_value=1)
                #r = jt_account.add_relations("authorize", test_address)
                logger.info("add_relations test:" + str(r))
                test_account_status = 14
            elif test_account_status == 14:
                #r = jt_account.get_relations(relations_type="authorize", counterparty=test_address, 
                #    currency="USD+"+test_issuer)
                r = jt_account.get_relations(relations_type="authorize")
                logger.info("get_relations test:" + str(r))
                test_account_status = 15
            elif test_account_status == 15:
                # error here
                try:
                    r = jt_account.get_counter_relations(test_address, test_secret, "authorize", "USD+"+test_issuer)
                    logger.info("get_counter_relations test:" + str(r))
                except Exception, e:
                    logger.error("get_counter_relations:" + str(e))       
                test_account_status = 16
            elif test_account_status == 16:
                # error here
                try:
                    r = jt_account.delete_relations("authorize", test_address, test_issuer, "USD")
                    logger.info("delete_relations test:" + str(r))
                except Exception, e:
                    logger.error("delete_relations:" + str(r)) 
                test_account_status = 17
            elif test_account_status == 17:
                r = jt_account.post_trustline(1, "USD", counterparty=test_issuer)
                logger.info("post_trustline test:" + str(r)) 
                test_account_status = 18
            elif test_account_status == 18:
                r = jt_account.get_trustlines()
                logger.info("get_trustlines test:" + str(r)) 
                test_account_status = 19
            else:
                #websockethelper.unsubscribe_message_by_account(jt_account.address)
                #websockethelper.close()
                logger.info("DONE") 
                break
            time.sleep(3)
        #except Exception, e:
        #    print "main error,", e
        #    break


        








"""API tests"""
import json
import unittest

import paket_stellar
import util.logger
import webserver.validation

import routes
import db

LOGGER = util.logger.logging.getLogger('pkt.api.test')
APP = webserver.setup(routes.BLUEPRINT)
APP.testing = True


def create_tables():
    """Create tables if they does not exists"""
    try:
        LOGGER.info('creating tables...')
        db.init_db()
    except db.util.db.mysql.connector.ProgrammingError:
        LOGGER.info('tables already exists')


def clear_tables():
    """Clear all tables in db"""
    assert db.DB_NAME.startswith('test'), "refusing to test on db named {}".format(db.DB_NAME)
    LOGGER.info('clearing database')
    db.util.db.clear_tables(db.SQL_CONNECTION, db.DB_NAME)


class PaketBaseTest(unittest.TestCase):
    """Base class for PaKeT tests."""

    @classmethod
    def setUpClass(cls):
        """Setting up class fixture before running tests."""
        create_tables()

    def setUp(self):
        """Setting up the test fixture before exercising it."""
        clear_tables()


class ApiBaseTest(PaketBaseTest):
    """Base class for routes tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = APP.test_client()
        self.host = 'http://localhost'
        self.funded_seed = 'SDJGBJZMQ7Z4W3KMSMO2HYEV56DJPOZ7XRR7LJ5X2KW6VKBSLELR7MRQ'
        self.funded_account = paket_stellar.get_keypair(seed=self.funded_seed)
        self.funded_pubkey = self.funded_account.address().decode()
        # GBTWWXA3CDQOSRQ3645B2L4A345CRSKSV6MSBUO4LSHC26ZMNOYFN2YJ
        LOGGER.info('init done')

    @staticmethod
    def sign_transaction(transaction, seed):
        """Sign transaction with provided seed"""
        builder = paket_stellar.stellar_base.builder.Builder(horizon=paket_stellar.HORIZON, secret=seed)
        builder.import_from_xdr(transaction)
        builder.sign()
        signed_transaction = builder.gen_te().xdr().decode()
        return signed_transaction

    def call(self, path, expected_code=None, fail_message=None, seed=None, **kwargs):
        """Post data to API server."""
        LOGGER.info("calling %s", path)
        if seed:
            fingerprint = webserver.validation.generate_fingerprint(
                "{}/v{}/{}".format(self.host, routes.VERSION, path), kwargs)
            signature = webserver.validation.sign_fingerprint(fingerprint, seed)
            headers = {
                'Pubkey': paket_stellar.get_keypair(seed=seed).address().decode(),
                'Fingerprint': fingerprint, 'Signature': signature}
        else:
            headers = None
        response = self.app.post("/v{}/{}".format(routes.VERSION, path), headers=headers, data=kwargs)
        response = dict(real_status_code=response.status_code, **json.loads(response.data.decode()))
        if expected_code:
            self.assertEqual(response['real_status_code'], expected_code, "{} ({})".format(
                fail_message, response.get('error')))
        return response

    def submit(self, transaction, seed=None, description='unknown'):
        """Submit a transaction, optionally adding seed's signature."""
        LOGGER.info("trying to submit %s transaction", description)
        if seed:
            transaction = self.sign_transaction(transaction, seed)
        return self.call(
            'submit_transaction', 200, "failed submitting {} transaction".format(description), transaction=transaction)

    def create_account(self, from_pubkey, new_pubkey, seed, starting_balance=50000000):
        """Create account with starting balance"""
        LOGGER.info('creating %s from %s', new_pubkey, from_pubkey)
        unsigned = self.call(
            'prepare_account', 200, 'could not get create account transaction',
            from_pubkey=from_pubkey, new_pubkey=new_pubkey, starting_balance=starting_balance)['transaction']
        response = self.submit(unsigned, seed, 'create account')
        return response

    def create_and_setup_new_account(self, amount_buls=None, trust_limit=None):
        """Create account. Add trust and send initial ammount of BULs (if specified)"""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        seed = keypair.seed().decode()
        self.create_account(from_pubkey=self.funded_pubkey, new_pubkey=pubkey, seed=self.funded_seed)
        self.trust(pubkey, seed, trust_limit)
        if amount_buls is not None:
            self.send(from_seed=self.funded_seed, to_pubkey=pubkey, amount_buls=amount_buls)
        return pubkey, seed

    def trust(self, pubkey, seed, limit=None):
        """Submit trust transaction for specified account"""
        LOGGER.info('adding trust for %s (%s)', pubkey, limit)
        unsigned = self.call(
            'prepare_trust', 200, 'could not get trust transaction', from_pubkey=pubkey, limit=limit)['transaction']
        return self.submit(unsigned, seed, 'add trust')

    def send(self, from_seed, to_pubkey, amount_buls):
        """Send BULs between accounts."""
        from_pubkey = paket_stellar.get_keypair(seed=from_seed).address().decode()
        description = "sending {} from {} to {}".format(amount_buls, from_pubkey, to_pubkey)
        LOGGER.info(description)
        unsigned = self.call(
            'prepare_send_buls', 200, "can not prepare send from {} to {}".format(from_pubkey, to_pubkey),
            from_pubkey=from_pubkey, to_pubkey=to_pubkey, amount_buls=amount_buls)['transaction']
        return self.submit(unsigned, from_seed, description)

    def prepare_escrow(self, payment, collateral, deadline):
        """Create launcher, courier, recipient, escrow accounts and call prepare_escrow"""
        LOGGER.info('preparing package accounts')
        launcher = self.create_and_setup_new_account(payment)
        courier = self.create_and_setup_new_account(collateral)
        recipient = self.create_and_setup_new_account()
        escrow = self.create_and_setup_new_account()

        LOGGER.info(
            "launching escrow: %s, launcher: %s, courier: %s, recipient: %s",
            escrow[0], launcher[0], courier[0], recipient[0])
        escrow_transactions = self.call(
            'prepare_escrow', 201, 'can not prepare escrow transactions', escrow[1],
            launcher_pubkey=launcher[0], courier_pubkey=courier[0], recipient_pubkey=recipient[0],
            payment_buls=payment, collateral_buls=collateral, deadline_timestamp=deadline)

        return {
            'launcher': launcher,
            'courier': courier,
            'recipient': recipient,
            'escrow': escrow,
            'transactions': escrow_transactions
        }


class DbBaseTest(PaketBaseTest):
    """Base class for db tests."""

    def generate_keypair(self):
        """Generate new stellar keypair."""
        keypair = paket_stellar.get_keypair()
        pubkey = keypair.address().decode()
        seed = keypair.seed().decode()
        return pubkey, seed

    def prepare_package_members(self):
        launcher = self.generate_keypair()
        courier = self.generate_keypair()
        recipient = self.generate_keypair()
        escrow = self.generate_keypair()
        return {
            'launcher': launcher, 'courier': courier,
            'recipient': recipient, 'escrow': escrow}

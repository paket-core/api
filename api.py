"""JSON swagger API to PaKeT."""
import logging
import os

import flasgger
import flask

import db
import paket
import swagger_specs
import webserver.validation

VERSION = swagger_specs.VERSION
PORT = os.environ.get('PAKET_API_PORT', 8000)
LOGGER = logging.getLogger('pkt.api')
BLUEPRINT = flask.Blueprint('api', __name__)

# Wallet routes.


@BLUEPRINT.route("/v{}/submit_transaction".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.SUBMIT_TRANSACTION)
@webserver.validation.call(['transaction'])
def submit_transaction_handler(transaction):
    """
    Submit a signed transaction.

    Use this call to submit a signed transaction.
    ---
    :param transaction:
    :return:
    """
    return {'status': 200, 'transaction': paket.submit_transaction_envelope(transaction)}


@BLUEPRINT.route("/v{}/bul_account".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.BUL_ACCOUNT)
@webserver.validation.call(['queried_pubkey'])
def bul_account_handler(queried_pubkey):
    """
    Get the details of your BUL account
    Use this call to get the balance and details of your account.
    ---
    :param queried_pubkey:
    :return:
    """
    return dict(status=200, **paket.get_bul_account(queried_pubkey))


@BLUEPRINT.route("/v{}/send_buls".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.SEND_BULS)
@webserver.validation.call(['to_pubkey', 'amount_buls'], require_auth=True)
def send_buls_handler(user_pubkey, to_pubkey, amount_buls):
    """
    Transfer BULs to another pubkey.
    Use this call to send part of your balance to another user.
    The to_pubkey can be either a user id, or a wallet pubkey.
    ---
    :param user_pubkey:
    :param to_pubkey:
    :param amount_buls:
    :return:
    """
    return {'status': 201, 'transaction': paket.send_buls(user_pubkey, to_pubkey, amount_buls)}


@BLUEPRINT.route("/v{}/prepare_send_buls".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_SEND_BULS)
@webserver.validation.call(['from_pubkey', 'to_pubkey', 'amount_buls'])
def prepare_send_buls_handler(from_pubkey, to_pubkey, amount_buls):
    """
    Transfer BULs to another pubkey.
    Use this call to prepare a transaction that sends part of your
    balance to another user. This function will return an unsigned
    transaction.  You can use the
    [laboratory](https://www.stellar.org/laboratory/#txsigner?network=test)
    to sign the transaction with your private key.  You can use the
    /recover_user call to find out your seed.  Than, you can either
    submit the signed transaction in the laboratory, or use the
    /submit_transaction call to send the signed transaction for
    submission.
    ---
    :param from_pubkey:
    :param to_pubkey:
    :param amount_buls:
    :return:
    """
    return {'status': 200, 'transaction': paket.prepare_send_buls(from_pubkey, to_pubkey, amount_buls)}


@BLUEPRINT.route("/v{}/price".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PRICE)
def price_handler():
    """
    Get buy and sell prices.
    ---
    :return:
    """
    return flask.jsonify({'status': 200, 'buy_price': 1, 'sell_price': 1})


# Package routes.


@BLUEPRINT.route("/v{}/launch_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.LAUNCH_PACKAGE)
@webserver.validation.call(
    ['recipient_pubkey', 'courier_pubkey', 'deadline_timestamp', 'payment_buls', 'collateral_buls'], require_auth=True)
def launch_package_handler(
        user_pubkey, recipient_pubkey, courier_pubkey, deadline_timestamp, payment_buls, collateral_buls):
    """
    Launch a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey:
    :param recipient_pubkey:
    :param courier_pubkey:
    :param deadline_timestamp:
    :param payment_buls:
    :param collateral_buls:
    :return:
    """
    return {
        'status': 201, **paket.launch_paket(
            user_pubkey, recipient_pubkey, courier_pubkey, deadline_timestamp, payment_buls, collateral_buls)}


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['paket_id'], require_auth=True)
def accept_package_handler(user_pubkey, paket_id, payment_transaction=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param paket_id:
    :param payment_transaction:
    :return:
    """
    paket.accept_package(user_pubkey, paket_id, payment_transaction)
    return {'status': 200}


@BLUEPRINT.route("/v{}/relay_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.RELAY_PACKAGE)
@webserver.validation.call(['paket_id', 'courier_pubkey', 'payment_buls'], require_auth=True)
def relay_package_handler(user_pubkey, paket_id, courier_pubkey, payment_buls):
    """
    Relay a package to another courier, offering payment.
    ---
    :param user_pubkey:
    :param paket_id:
    :param courier_pubkey:
    :param payment_buls:
    :return:
    """
    return {'status': 200, 'transaction': paket.relay_payment(user_pubkey, paket_id, courier_pubkey, payment_buls)}


@BLUEPRINT.route("/v{}/refund_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.REFUND_PACKAGE)
@webserver.validation.call(['paket_id', 'refund_transaction'], require_auth=True)
# pylint: disable=unused-argument
# user_pubkey is used in decorator.
def refund_package_handler(user_pubkey, paket_id, refund_transaction):
    """
    Relay a package to another courier, offering payment.
    ---
    :param user_pubkey:
    :param paket_id:
    :param refund_transaction:
    :return:
    """
    # pylint: enable=unused-argument
    return {'status': 200, 'transaction': paket.refund(paket_id, refund_transaction)}


# pylint: disable=unused-argument
# This function does not yet implement the filters.
@BLUEPRINT.route("/v{}/my_packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.MY_PACKAGES)
@webserver.validation.call(require_auth=True)
def my_packages_handler(user_pubkey, show_inactive=False, from_date=None, role_in_delivery=None):
    """
    Get list of packages
    Use this call to get a list of packages.  You can filter the list by
    showing only active packages, or packages originating after a
    certain date.  You can also filter to show only packages where the
    user has a specific role, such as "launcher" or "receiver".
    ---
    :param user_pubkey:
    :param show_inactive:
    :param from_date:
    :param role_in_delivery:
    :return:
    """
    return {'status': 200, 'packages': db.get_packages()}
# pylint: enable=unused-argument


@BLUEPRINT.route("/v{}/package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE)
@webserver.validation.call(['paket_id'])
def package_handler(paket_id):
    """
    Get a full info about a single package.
    ---
    :param paket_id:
    :return:
    """
    return {'status': 200, 'package': db.get_package(paket_id)}


# User routes.


@BLUEPRINT.route("/v{}/register_user".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.REGISTER_USER)
@webserver.validation.call(['full_name', 'phone_number', 'paket_user'], require_auth=True)
# Note that pubkey is different from user_pubkey in that it does not yet exist in the system.
def register_user_handler(user_pubkey, full_name, phone_number, paket_user):
    """
    Register a new user.
    ---
    :param user_pubkey:
    :param full_name:
    :param phone_number:
    :param paket_user:
    :return:
    """
    try:
        paket.stellar_base.keypair.Keypair.from_address(str(user_pubkey))
        db.create_user(user_pubkey, paket_user)

    # For debug purposes, we generate a pubkey if no valid key is found.
    except paket.stellar_base.utils.DecodeError:
        if not webserver.validation.DEBUG:
            raise webserver.validation.InvalidField("invalid pubkey {}".format(user_pubkey))
        keypair = paket.get_keypair()
        user_pubkey, seed = keypair.address().decode(), keypair.seed().decode()
        db.create_user(user_pubkey, paket_user, seed)
        paket.new_account(user_pubkey)
        paket.trust(keypair)

    return {'status': 201, 'user_details': db.update_user_details(user_pubkey, full_name, phone_number)}


@BLUEPRINT.route("/v{}/recover_user".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.RECOVER_USER)
@webserver.validation.call(require_auth=True)
def recover_user_handler(user_pubkey):
    """
    Recover user details.

    TODO about the seed
    ---
    :param user_pubkey:
    :return:
    """
    return {'status': 200, 'user_details': db.get_user(user_pubkey)}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/users".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.USERS)
@webserver.validation.call
def users_handler():
    """
    Get a list of users and their details - for debug only.
    ---
    :return:
    """
    return {'status': 200, 'users': {
        pubkey: dict(user, bul_account=paket.get_bul_account(pubkey)) for pubkey, user in db.get_users().items()}}


@BLUEPRINT.route("/v{}/debug/packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGES)
@webserver.validation.call
def packages_handler():
    """
    Get list of packages - for debug only.
    ---
    :return:
    """
    return {'status': 200, 'packages': db.get_packages()}


# Sandbox setup.


def create_db_user(paket_user, pubkey):
    """Create a new user in the DB."""
    LOGGER.debug("Creating user %s", paket_user)
    try:
        db.create_user(pubkey, paket_user)
        db.update_user_details(pubkey, paket_user, '123-456')
        webserver.validation.update_nonce(pubkey, 1, paket_user)
    except db.DuplicateUser:
        LOGGER.debug("User %s already exists", paket_user)


def init_sandbox():
    """Initialize database with debug values and fund users. For debug only."""
    webserver.validation.init_nonce_db()
    db.init_db()
    for paket_user, pubkey in [
            (key.split('PAKET_USER_', 1)[1], value)
            for key, value in os.environ.items()
            if key.startswith('PAKET_USER_')
    ]:
        create_db_user(paket_user, pubkey)


if __name__ == '__main__':
    webserver.run(BLUEPRINT, swagger_specs.CONFIG, PORT)

"""JSON swagger API to PaKeT."""
import os

import flasgger
import flask

import paket_stellar
import util.logger
import util.conversion
import webserver.validation

import db
import swagger_specs

LOGGER = util.logger.logging.getLogger('pkt.api')
VERSION = swagger_specs.VERSION
PORT = os.environ.get('PAKET_API_PORT', 8000)
BLUEPRINT = flask.Blueprint('api', __name__)


# Input validators and fixers.
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_timestamp'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_buls'] = webserver.validation.check_and_fix_natural
webserver.validation.KWARGS_CHECKERS_AND_FIXERS['_num'] = webserver.validation.check_and_fix_natural


# Wallet routes.


@BLUEPRINT.route("/v{}/submit_transaction".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.SUBMIT_TRANSACTION)
@webserver.validation.call(['transaction'])
def submit_transaction_handler(transaction):
    """
    Submit a signed transaction. This call is used to submit signed
    transactions. Signed transactions can be obtained by signing unsigned
    transactions returned by other calls. You can use the
    [laboratory](https://www.stellar.org/laboratory/#txsigner?network=test) to
    sign the transaction with your private key.
    ---
    :param transaction:
    :return:
    """
    return {'status': 200, 'response': paket_stellar.submit_transaction_envelope(transaction)}


@BLUEPRINT.route("/v{}/bul_account".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.BUL_ACCOUNT)
@webserver.validation.call(['queried_pubkey'])
def bul_account_handler(queried_pubkey):
    """
    Get the details of a Stellar BUL account.
    ---
    :param queried_pubkey:
    :return:
    """
    account = paket_stellar.get_bul_account(queried_pubkey)
    return dict(status=200, **account)


@BLUEPRINT.route("/v{}/prepare_account".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_ACCOUNT)
@webserver.validation.call(['from_pubkey', 'new_pubkey'])
def prepare_account_handler(from_pubkey, new_pubkey, starting_balance=50000000):
    """
    Prepare a create account transaction.
    ---
    :param from_pubkey:
    :param new_pubkey:
    :param starting_balance:
    :return:
    """
    try:
        return {'status': 200, 'transaction': paket_stellar.prepare_create_account(
            from_pubkey, new_pubkey, starting_balance)}
    # pylint: disable=broad-except
    # stellar_base throws this as a broad exception.
    except Exception as exception:
        LOGGER.info(str(exception))
        if str(exception) == 'No sequence is present, maybe not funded?':
            return {'status': 400, 'error': "{} is not a funded account".format(from_pubkey)}
        raise
    # pylint: enable=broad-except


@BLUEPRINT.route("/v{}/prepare_trust".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_TRUST)
@webserver.validation.call(['from_pubkey'])
def prepare_trust_handler(from_pubkey, limit=None):
    """
    Prepare an add trust transaction.
    ---
    :param from_pubkey:
    :param limit:
    :return:
    """
    return {'status': 200, 'transaction': paket_stellar.prepare_trust(from_pubkey, limit)}


@BLUEPRINT.route("/v{}/prepare_send_buls".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_SEND_BULS)
@webserver.validation.call(['from_pubkey', 'to_pubkey', 'amount_buls'])
def prepare_send_buls_handler(from_pubkey, to_pubkey, amount_buls):
    """
    Prepare a BUL transfer transaction.
    ---
    :param from_pubkey:
    :param to_pubkey:
    :param amount_buls:
    :return:
    """
    return {'status': 200, 'transaction': paket_stellar.prepare_send_buls(from_pubkey, to_pubkey, amount_buls)}


# Package routes.


@BLUEPRINT.route("/v{}/prepare_escrow".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PREPARE_ESCROW)
@webserver.validation.call(
    ['launcher_pubkey', 'recipient_pubkey', 'courier_pubkey', 'payment_buls', 'collateral_buls', 'deadline_timestamp'],
    require_auth=True)
def prepare_escrow_handler(
        user_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp, location=None):
    """
    Launch a package.
    Use this call to create a new package for delivery.
    ---
    :param user_pubkey: the escrow pubkey
    :param launcher_pubkey:
    :param courier_pubkey:
    :param recipient_pubkey:
    :param payment_buls:
    :param collateral_buls:
    :param deadline_timestamp:
    :param location:
    :return:
    """
    package_details = paket_stellar.prepare_escrow(
        user_pubkey, launcher_pubkey, courier_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp)
    db.create_package(**dict(package_details, location=location))
    return dict(status=201, **package_details)


@BLUEPRINT.route("/v{}/accept_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ACCEPT_PACKAGE)
@webserver.validation.call(['escrow_pubkey'], require_auth=True)
def accept_package_handler(user_pubkey, escrow_pubkey, location=None):
    """
    Accept a package.
    If the package requires collateral, commit it.
    If user is the package's recipient, release all funds from the escrow.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :return:
    """
    package = db.get_package(escrow_pubkey)
    event_type = 'received' if package['recipient_pubkey'] == user_pubkey else 'couriered'
    db.add_event(escrow_pubkey, user_pubkey, event_type, location)
    return {'status': 200}


@BLUEPRINT.route("/v{}/my_packages".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.MY_PACKAGES)
@webserver.validation.call(require_auth=True)
def my_packages_handler(user_pubkey):
    """
    Get list of packages concerning the user.
    ---
    :param user_pubkey:
    :return:
    """
    packages = db.get_packages(user_pubkey)
    return {'status': 200, 'packages': packages}


@BLUEPRINT.route("/v{}/package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.PACKAGE)
@webserver.validation.call(['escrow_pubkey'])
def package_handler(escrow_pubkey):
    """
    Get a full info about a single package.
    ---
    :param escrow_pubkey:
    :return:
    """
    package = db.get_package(escrow_pubkey)
    return {'status': 200, 'package': package}


@BLUEPRINT.route("/v{}/add_event".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.ADD_EVENT)
@webserver.validation.call(['escrow_pubkey', 'event_type', 'location'], require_auth=True)
def add_event_handler(user_pubkey, escrow_pubkey, event_type, location):
    """
    (Deprecated)
    Add new event for package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param event_type:
    :param location:
    :return:
    """
    LOGGER.warning("/v%s/add_event is deprecated and will be removed in future", VERSION)
    db.add_event(escrow_pubkey, user_pubkey, event_type, location)
    return {'status': 200}


@BLUEPRINT.route("/v{}/changed_location".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CHANGED_LOCATION)
@webserver.validation.call(['escrow_pubkey', 'location'], require_auth=True)
def changed_location_handler(user_pubkey, escrow_pubkey, location):
    """
    Add new `changed_location` event for package.
    ---
    :param user_pubkey:
    :param escrow_pubkey:
    :param location:
    :return:
    """
    db.add_event(escrow_pubkey, user_pubkey, 'changed location', location)
    return {'status': 200}


# Debug routes.


@BLUEPRINT.route("/v{}/debug/fund".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.FUND_FROM_ISSUER)
@webserver.validation.call(['funded_pubkey'])
def fund_handler(funded_pubkey, funded_buls=1000000000):
    """
    Give an account BULs - for debug only.
    ---
    :return:
    """
    return {'status': 200, 'response': paket_stellar.fund_from_issuer(funded_pubkey, funded_buls)}


@BLUEPRINT.route("/v{}/debug/create_mock_package".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.CREATE_MOCK_PACKAGE)
@webserver.validation.call(
    ['escrow_pubkey', 'launcher_pubkey', 'recipient_pubkey', 'payment_buls', 'collateral_buls', 'deadline_timestamp'])
def create_mock_package_handler(
        escrow_pubkey, launcher_pubkey, recipient_pubkey,
        payment_buls, collateral_buls, deadline_timestamp):
    """
    Create a mock package - for debug only.
    ---
    :return:
    """
    return {'status': 201, 'package': db.create_package(
        escrow_pubkey, launcher_pubkey, recipient_pubkey, payment_buls, collateral_buls, deadline_timestamp,
        'mock_setopts', 'mock_refund', 'mock merge', 'mock payment')}


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


@BLUEPRINT.route("/v{}/events".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.EVENTS)
@webserver.validation.call
def events_handler(limit=100, allow_mock=False):
    """
    Get all events.
    ---
    :return:
    """
    events = db.get_events(limit=limit)
    if (not events['packages_events'] and not events['user_events']) and allow_mock:
        events = {
            'packages_events': [
                {'timestamp': '2018-08-03 14:29:18.116482',
                 'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                 'user_pubkey': 'GBUPZ63WK2ZLOCXPCUOMM7XRUGXOVJC3RIBL7KBTUSHLKFRKVHUB757L',
                 'event_type': 'launched', 'location': '51.4983407,-0.173709'},
                {'timestamp': '2018-08-03 14:35:05.958315',
                 'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                 'user_pubkey': 'GCBKJ3QLHCBK5WBF4UZ5K2LOVDI63WG2SKLIWIMREPRLCTIHD6B5QR65',
                 'event_type': 'couriered', 'location': '51.4983407,-0.173709'},
                {'timestamp': '2018-08-04 17:02:55.138572',
                 'escrow_pubkey': 'GB5SUIN2OEJXG2GDYG6EGB544DQLUVZX35SJJVLHWCEZ4FYWRWW236FB',
                 'user_pubkey': 'GDRGF2BU7CV4QU4E54B72BJEL4CWFMTTVSVJMKWESK32HLTYD4ZEWJOR',
                 'event_type': 'received', 'location': '53.3979468,-2.932953'},
                {'timestamp': '2018-08-03 06:35:17.169421',
                 'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                 'user_pubkey': 'GANEU37FIEBICW6352CVIUD7GYOV5H7W5YUE5ECDH5PJNF7R5ISYJR3K',
                 'event_type': 'launched', 'location': '31.2373787,34.7889161'},
                {'timestamp': '2018-08-03 07:01:17.192375',
                 'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                 'user_pubkey': 'GBL4FZ6HCA6SQATD5UYHQYMVWASBEZCKGL2P7PEU6VNLONVFZY6DPV3R',
                 'event_type': 'couriered', 'location': '31.2373787,34.7889161'},
                {'timestamp': '2018-08-05 22:05:53.162485',
                 'escrow_pubkey': 'GBMU5SWBUNBCDRUMIZNCDOTMIRGLBFY5DEPIE4OTBAUOFK4V3HOENAGT',
                 'user_pubkey': 'GBYYI24HZ75OYBAHZOUVAAQNS5YHMN32VLCDBZFXHAAJKRRSCZICBIDJ',
                 'event_type': 'received', 'location': '32.8266712,34.9774087'},
                {'timestamp': '2018-08-07 05:55:15.168276',
                 'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                 'user_pubkey': 'GAZ2UUQUEYY2LHAQMP4M737DXXX3TM7L6BE5JT7LYWS5GYL6VXQ6HASR',
                 'event_type': 'launched', 'location': '12.926039,77.5056131'},
                {'timestamp': '2018-08-07 09:14:18.137124',
                 'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                 'user_pubkey': 'GBQR3QGZOS2K4MQPPJDKRMJ6MIEACCG4BRO23UE33TDFRZOM57VL5O5J',
                 'event_type': 'couriered', 'location': '12.926039,77.5056131'},
                {'timestamp': '2018-08-09 14:27:16.143762',
                 'escrow_pubkey': 'GALIFYZ6GDHXWDH2QZLRJY2XS77A6WXILDFSRH6ZZM3IYOIH2XEK3TAK',
                 'user_pubkey': 'GAYOZB7SZBD7O4UPLLQNXFN5ZZCQJSXBKERNIY4MIWL7DVXF7DBF7OU6',
                 'event_type': 'received', 'location': '28.7050581,77.1419526'}
            ],
            'user_events': [
                {'timestamp': '2018-08-01 17:46:18.169723',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GBUPZ63WK2ZLOCXPCUOMM7XRUGXOVJC3RIBL7KBTUSHLKFRKVHUB757L',
                 'event_type': 'installed app', 'location': '51.5482912,-0.3048464'},
                {'timestamp': '2018-07-22 19:36:18.123142',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GCCYNSN3WETV2FBASFVXKAJ54OX4NUTP4ZUJFGXTX47A2GRQYQ52QQBK',
                 'event_type': 'installed app', 'location': '50.2443519,28.6989147'},
                {'timestamp': '2018-07-22 19:58:38.164237',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GCCYNSN3WETV2FBASFVXKAJ54OX4NUTP4ZUJFGXTX47A2GRQYQ52QQBK',
                 'event_type': 'passed kyc', 'location': '50.2443519,28.6989147'},
                {'timestamp': '2018-07-28 05:34:21.134562',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GBOTDKM6ZJNV54QLXKTU5WSYFXJZDZZSGKTYHDNWDDVAEVB73DPLSP4H',
                 'event_type': 'funded account', 'location': '22.9272893,113.3443182'},
                {'timestamp': '2018-07-30 22:12:21.136421',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GAUHIJXEV2D46G375FJNCUBGVUKXRF7C3VC7U3HUPCBIZUYHJKP4N6XA',
                 'event_type': 'funded account', 'location': '-16.2658233,-47.9159335'},
                {'timestamp': '2018-08-03 17:35:14.136415',
                 'escrow_pubkey': None,
                 'user_pubkey': 'GAL54ATIHYBWMKYUNQSM3QAGZGCUBJGF6KEFFSQTEV7JOOA72UEJP4UL',
                 'event_type': 'funded account', 'location': '51.0465554,-114.0752757'}
            ]}
    return {'status': 200, 'events': events}


@BLUEPRINT.route("/v{}/debug/log".format(VERSION), methods=['POST'])
@flasgger.swag_from(swagger_specs.LOG)
@webserver.validation.call
def view_log_handler(lines_num=10):
    """
    Get last lines of log - for debug only.
    Specify lines_num to get the x last lines.
    """
    with open(os.path.join(util.logger.LOG_DIR_NAME, util.logger.LOG_FILE_NAME)) as logfile:
        return {'status': 200, 'log': logfile.readlines()[:-1 - lines_num:-1]}

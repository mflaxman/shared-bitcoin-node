from bitcoinrpc import BitcoinRPC
from bitcoinrpc.bitcoin_rpc import RPCError

from os import environ

from sanic import Sanic
from sanic.response import json


CORE_HOST = environ.get("CORE_HOST", "localhost")
CORE_PORT = int(environ.get("CORE_PORT", "18332"))  # default to testnet
CORE_USER = environ.get("CORE_USER")
if not CORE_USER:
    raise Exception("Must supply CORE_USER")
CORE_PASSWORD = environ.get("CORE_PASSWORD")
if not CORE_PASSWORD:
    raise Exception("Must supply CORE_PASSWORD")


PYTHON_HOST = environ.get("PYTHON_HOST", "0.0.0.0")
PYTHON_PORT = int(environ.get("PYTHON_PORT", "8000"))

print(
    "Remote Bitcoin Core RPC Server: %s@%s:%s:%s"
    % (CORE_USER, CORE_PASSWORD, CORE_HOST, CORE_PORT)
)

rpc = BitcoinRPC(CORE_HOST, CORE_PORT, CORE_USER, CORE_PASSWORD)

app = Sanic("Python Bitcoin Core Node Wrapper")

ACCEPTABLE_RPC_METHODS = {
    "combinepsbt",
    "createwallet",
    "decodepsbt",
    "deriveaddresses",
    "estimatesmartfee",
    "getaddressesbylabel",
    "getaddressinfo",
    "getbalances",
    "getblockchaininfo",
    "getblockcount",
    "getblockhash",
    "getdescriptorinfo",
    "getmempoolinfo",
    "getmininginfo",
    "getnetworkinfo",
    "getnewaddress",
    "getpeerinfo",
    "getreceivedbyaddress",
    "gettransaction",
    "gettxoutproof",
    "getwalletinfo",
    "getblockfilter",
    "help",  # this output will not be 100% accurate
    "importmulti",
    "loadwallet",
    "lockunspent",
    "listlabels",
    "listlockunspent",
    "listsinceblock",
    "listtransactions",
    "listunspent",
    "listwalletdir",
    "listwallets",
    "scantxoutset",
    "setlabel",
    "uptime",
    "walletcreatefundedpsbt",
    "walletprocesspsbt",
}


def make_error(message, code=None):
    if not code:
        # random error for all wrapper functions:
        code = -2020
    return {
        "error": {
            "message": message,
            "code": code,
        },
        "result": None,
    }


def make_success(result):
    return {
        "result": result,
        "error": None,
    }


async def make_singleton(method, params, new_path=None):
    if method not in ACCEPTABLE_RPC_METHODS:
        print("Unsupported RPC call", method)
        return make_error(message="Unsupported RPC call: %s" % method)

    if not params:
        params = []
    try:
        for param in params:
            if type(param) is dict:
                if "rescan" in param:
                    param["rescan"] = False
                    print("*" * 88)
                    print("RESCAN DATA FOUND")
        if new_path:
            rpc._url = f"http://{CORE_HOST}:{CORE_PORT}/{new_path}"

        res = await rpc.acall(method, params)

        if new_path:
            # Set pack bath. Check for race conditions and/or migrate away from this library!?
            rpc._url = f"http://{CORE_HOST}:{CORE_PORT}"
        print("SUCCESS", res)
        return make_success(res)
    except RPCError as e:
        print("ERROR", e.code, e.message)
        return make_error(code=e.code, message=e.message)


# This is a catch-all in case of bizarre /wallet behavior from specter-desktop
@app.post("/")
@app.post("/<path:path>")
async def wrapper(request, path=None):
    if path:
        print("path", path)
    print("request.args", request.args)
    print("request.query_string", request.query_string)
    print("request.url", request.url)
    print("request.json", request.json)
    print("request.form", request.form)

    if type(request.json) is not list:
        print("SINGLETON")

        if "method" not in request.json:
            print("Malformed request lacks method", request.json)
            return json(make_error(message="malformed request: no method supplied"))

        to_return = await make_singleton(
            method=request.json["method"],
            params=request.json.get("params"),
            new_path=path,
        )
        return json(to_return)

    print("MUTLI")
    if len(request.json) == 0:
        print("BAD MULTI, empty list")
        return json(make_error(message="empty-list"))

    # Safety check
    to_return = []
    for req in request.json:
        if "method" not in req:
            print("Malformed request item lacks method", req)
            to_return.append(
                make_error(message="malformed request item: no method supplied")
            )
            continue

        res = await make_singleton(
            method=req["method"], params=req.get("params"), new_path=path
        )
        to_return.append(res)
    return json(to_return)


if __name__ == "__main__":
    print("Running python server on %s:%s" % (PYTHON_HOST, PYTHON_PORT))
    app.run(host=PYTHON_HOST, port=PYTHON_PORT)

import tomllib
import argparse
import pathlib

import web3
import requests
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_hex
from solana.rpc.api import Client
from solana.transaction import Signature


def check_tx_exist(tx_hash: str, operator_url: str):
    w = web3.Web3(web3.HTTPProvider(operator_url))
    return w.eth.get_transaction(HexBytes(tx_hash)) is not None


def check_receipt_exist(tx_hash: str, operator_url: str):
    w = web3.Web3(web3.HTTPProvider(operator_url))
    return w.eth.get_transaction_receipt(HexBytes(tx_hash)) is not None


def debug_transaction(tx_hash: str, operator_url: str, solana_url: str):
    w3 = web3.Web3(web3.HTTPProvider(operator_url))
    tx_info = requests.post(operator_url, json={
        "jsonrpc": "2.0",
        "method": "neon_getTransactionReceipt",
        "params": [tx_hash],
        "id": 1
    }).json()
    if "result" not in tx_info:
        print("Got a problem with transaction info: ", tx_info)
        return
    tx_info = tx_info["result"]
    status = "Failed" if tx_info["status"] == '0x0' else "Success"
    gas = w3.eth.get_transaction(HexBytes(tx_hash)).gas
    gas_used = int(tx_info["gasUsed"], 16)
    solana_txs = len(tx_info["solanaTransactions"])

    print(f"Status: {status}")
    print(f"Estimated gas: {gas} | Gas used: {gas_used} {gas_used / gas * 100:.2f}%")
    print(f"Solana transactions: {solana_txs}")

    if status == "Success":
        return

    sol_client = Client(solana_url)
    failed_sol_tx = []
    reasons = {}
    for sol_tx in tx_info["solanaTransactions"]:
        if sol_tx["solanaTransactionIsSuccess"] is False:
            failed_sol_tx.append(sol_tx["solanaTransactionSignature"])
    if len(failed_sol_tx) == 0:
        print(f"Transaction {tx_hash} is failed but no failed solana transaction found")
        return

    print(f"Solana failed transactions: {len(failed_sol_tx)}")
    for failed_sol_tx in failed_sol_tx:
        solana_tx_details = sol_client.get_transaction(Signature.from_string(failed_sol_tx), max_supported_transaction_version=0)
        if solana_tx_details is None or solana_tx_details.value is None:
            print(f"Transaction {tx_hash} is failed but no failed solana transaction found")
            return

        logs = solana_tx_details.value.transaction.meta.log_messages
        reasons[failed_sol_tx] = logs[-1]

        filename = f"logs/{failed_sol_tx}.log"
        with open(filename, "w") as f:
            f.write("\n".join(logs))

    print(f"Failed Solana transaction: {failed_sol_tx}")
    print(f"Reasons:")
    for tx, reason in reasons.items():
        print(f"    {tx}: {reason}")
    print(f"Full log saved in 'logs' folder")


if __name__ == '__main__':
    with open("config.toml", "b+r") as f:
        config = tomllib.load(f)

    parser = argparse.ArgumentParser(description="Check transaction exist in operators")
    parser.add_argument(
        "--network",
        type=str,
        default="mainnet",
        help="Solana network name",
    )

    parser.add_argument(
        type=str,
        dest="tx_hash",
        help="Neon transaction hash",
    )

    parser.add_argument(
        "--logs",
        action="store_true",
        help="Output logs of failed solana transactions to stdout",
    )
    args = parser.parse_args()

    if args.network not in config["solana"]:
        print("Network not found")
        exit(1)

    if not (is_hex(args.tx_hash) and len(args.tx_hash) == 66):
        print(args.tx_hash)
        print("Invalid transaction hash")
        exit(1)

    if not pathlib.Path("logs").exists():
        pathlib.Path("logs").mkdir()

    transaction_operator = None
    print("Verify transaction exist in operators")
    print("-------------------------------------")
    for eth_network, url in config["rpc"].items():
        result = check_tx_exist(args.tx_hash, url)
        if result:
            transaction_operator = eth_network
            result = "Exist"
        else:
            result = "Not exist"
        print(f"{eth_network}: {result}")

    if not transaction_operator:
        print("Transaction not found in operators")
        exit(1)

    receipt_operator = None
    print("\nVerify receipt exist in operators")
    print("---------------------------------")
    for eth_network, url in config["rpc"].items():
        result = check_receipt_exist(args.tx_hash, url)
        if result:
            receipt_operator = eth_network
            result = "Exist"
        else:
            result = "Not exist"
        result = "Exist" if result else "Not exist"
        print(f"{eth_network}: {result}")

    if not receipt_operator:
        print("Receipt not found in operators")
        exit(1)

    print("\nProvide more information about transaction")
    print("------------------------------------------")
    debug_transaction(args.tx_hash, config["rpc"][receipt_operator], config["solana"][args.network])

    if args.logs:
        print("\nLogs of failed solana transactions")
        print("-----------------------------------")
        for log in pathlib.Path("logs").iterdir():
            print(f"---- Log from file: {log}")
            with open(log, "r") as f:
                print(f.read())
"""Fetch the latest NHSN weekly data and store in the archives"""

import argparse
import os
import shutil
from pathlib import Path
import warnings

import pandas as pd

from utils.nhsn_data import (
    fetch_nhsn_hosp_data, get_latest_nhsn_url_and_metadata, get_data_url, send_and_check_request, get_metadata_url
)


# ===============


def main():
    args = parse_args()

    # --- Parameters
    output_dir = Path("./datasets/nhsn_weekly_jurisdiction")
    # preliminary = args.preliminary
    arg_release: str = args.release
    now: pd.Timestamp = args.now
    save_latest = args.save_latest
    export: bool = args.export

    if not export:
        warnings.warn("The --export switch is off. No outputs will be generated.")

    # ----
    # Decide which data release to fetch and get NHSN metadata
    url, metadata_dict, release = choose_data_url_and_get_metadata(arg_release)

    nhsn_df = fetch_nhsn_hosp_data(
        request_url=url,
        parse_dates=True,
    )

    if export:
        arch_fname = output_dir / f"nhsn_{now.date().isoformat()}.csv"
        print(f"Exporting to {arch_fname}...")
        output_dir.mkdir(parents=True, exist_ok=True)
        nhsn_df.to_csv(arch_fname, index=False)
        print("Exporting done.")

        if save_latest:
            latest_fname = output_dir / f"nhsn_latest.csv"
            print(f"Exporting to {latest_fname}...")
            shutil.copy2(
                src=arch_fname,
                dst=latest_fname,
            )
            print("Exporting done")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--now",
        type=pd.Timestamp,
        help="Change the date and time regarded as 'now' by the program."
             " Defaults to pd.Timestamp.now(tz='America/New_York')",
        default=pd.Timestamp.now(tz='America/New_York')
    )

    parser.add_argument(
        "--release", "-r",
        type=str,
        help="Which release of the NHSN respiratory data should be "
             "fetched: consolidated (Friday release), preliminary "
             "(Wednesday release) or latest available. Defaults to latest.",
        choices=["latest", "preliminary", "prelim", "consolidated", "consol"],
        default="latest",
    )

    parser.add_argument(
        "--export",
        action=argparse.BooleanOptionalAction,
        help="Whether to produce any outputs to files. Use `--no-export` "
             "to suppress outputs.",
        default=True,
    )

    parser.add_argument(
        "--save-latest",
        type=bool,
        help="Whether the fetched data should also be saved as 'latest.csv'",
        default=True,
    )

    parser.add_argument(
        "--fetch-trigger",
        type=str,
        help="Specifies the event that triggered the data fetch request, "
             "to include in the file metadata.",
        default="manual",
    )

    return parser.parse_args()


def choose_data_url_and_get_metadata(release):
    if release in ["prelim", "preliminary"]:
        url = get_data_url("prelim")
        release = "prelim"
        metadata_dict = send_and_check_request(get_metadata_url("prelim")).json()
    elif release in ["consol", "consolidated"]:
        url = get_data_url("consol")
        release = "consol"
        metadata_dict = send_and_check_request(get_metadata_url("consol")).json()
    elif release in ["latest"]:
        url, metadata_dict, release = get_latest_nhsn_url_and_metadata()
    else:
        raise ValueError(
            f"Unrecognized value for parameter `release`: {release}")

    return url, metadata_dict, release


if __name__ == "__main__":
    main()

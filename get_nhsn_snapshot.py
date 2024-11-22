"""Fetch the latest NHSN weekly data and store in the archives"""

import argparse
import os
import shutil
from pathlib import Path

import pandas as pd

from utils.nhsn_data import fetch_nhsn_hosp_data


# ===============


def main():
    args = parse_args()

    # Params
    output_dir = Path("./datasets/nhsn_weekly_jurisdiction")
    preliminary = args.preliminary
    now: pd.Timestamp = args.now
    is_latest = args.is_latest

    # ----

    if preliminary:
        url = "https://data.cdc.gov/resource/mpgq-jmmr.json"
    else:
        url = "https://data.cdc.gov/resource/ua7e-t2fy.json"

    nhsn_df = fetch_nhsn_hosp_data(
        request_url=url,
        parse_dates=True,
    )

    arch_fname = output_dir / f"nhsn_{now.date().isoformat()}.csv"
    print(f"Exporting to {arch_fname}...")
    output_dir.mkdir(parents=True, exist_ok=True)
    nhsn_df.to_csv(arch_fname)
    print("Exporting done.")

    if is_latest:
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
        "--preliminary",
        type=bool,
        help="Whether to use the preliminary NHSN data instead of the "
             "consolidated one. The preliminary data is released on"
             "the Wednsesday before the conosolidate data. While "
             "incomplete, it provides earlier access to the latest "
             "time point data.",
        default=True,
        action=argparse.BooleanOptionalAction,
    )

    parser.add_argument(
        "--now",
        type=pd.Timestamp,
        help="Change the date and time regarded as 'now' by the program."
             " Defaults to pd.Timestamp.now(tz='America/New_York')",
        default=pd.Timestamp.now(tz='America/New_York')
    )

    parser.add_argument(
        "--is-latest",
        type=bool,
        help="Whether the fetched data is considered latest and thus "
             "must be saved as 'latest.csv'",
        default=True,
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()

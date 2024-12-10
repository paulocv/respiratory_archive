"""Fetch the latest NHSN weekly data and store in the archives"""

import argparse
import os
import shutil
from pathlib import Path
import warnings

import pandas as pd

from utils.nhsn_data import fetch_nhsn_hosp_data, get_latest_nhsn_url, get_data_url


# ===============


def main():
    args = parse_args()

    # --- Parameters
    output_dir = Path("./datasets/nhsn_weekly_jurisdiction")
    # preliminary = args.preliminary
    release = args.release
    now: pd.Timestamp = args.now
    save_latest = args.save_latest
    export: bool = args.export

    if not export:
        warnings.warn("The --export switch is off. No outputs will be generated.")

    # ----

    url = choose_data_url(release)

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

    # parser.add_argument(
    #     "--preliminary",
    #     type=bool,
    #     help="Whether to use the preliminary NHSN data instead of the "
    #          "consolidated one. The preliminary data is released on"
    #          "the Wednsesday before the conosolidate data. While "
    #          "incomplete, it provides earlier access to the latest "
    #          "time point data.",
    #     default=True,
    #     action=argparse.BooleanOptionalAction,
    # )

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

    return parser.parse_args()


def choose_data_url(release):
    if release in ["prelim", "preliminary"]:
        return get_data_url("preliminary")
    elif release in ["consol", "consolidated"]:
        return get_data_url("consolidated")
    elif release in ["latest"]:
        return get_latest_nhsn_url()
    else:
        raise ValueError(
            f"Unrecognized value for parameter `release`: {release}")


if __name__ == "__main__":
    main()

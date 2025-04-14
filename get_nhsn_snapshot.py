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
from utils.yaml_tools import load_yaml, save_yaml


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
    update_metadata: bool = args.update_metadata

    if not export:
        warnings.warn("The --export switch is off. No outputs will be generated.")

    # ----

    dataset_metadata = load_yaml(output_dir / "metadata.yaml")

    # Decide which data release to fetch and get NHSN metadata
    url, nhsn_metadata, release = choose_data_url_and_get_metadata(arg_release)

    nhsn_df = fetch_nhsn_hosp_data(
        request_url=url,
        parse_dates=True,
    )

    print(nhsn_df.sort_values("weekendingdate", ascending=False).head())  # WATCHPOINT

    export_outputs(
        nhsn_metadata, nhsn_df, dataset_metadata, args, now, release,
        output_dir, export, save_latest, update_metadata
    )


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
        "--update-metadata",
        help="Whether to update the metadata if new data is fetched.",
        action=argparse.BooleanOptionalAction,
        default=True
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


def make_nhsn_file_metadata():
    """Create an entry in the metadata file for the NHSN data."""

    # return


def export_outputs(
        nhsn_metadata: pd.DataFrame,
        nhsn_df: pd.DataFrame,
        dataset_metadata: dict,
        args,
        now: pd.Timestamp,
        release: str,
        output_dir: Path,
        export: bool,
        save_latest: bool,
        update_metadata: bool,
):
    if not export:
        print("EXPORT SKIPPED")
        return

    # filename = f"nhsn_{now.date().isoformat()}.csv"
    date_str = pd.Timestamp(nhsn_metadata['dataUpdatedAt']).date().isoformat()
    filename = f"nhsn_{date_str}.csv"
    arch_fpath = output_dir / filename
    print(f"Exporting to {arch_fpath}...")
    if arch_fpath.exists():
        warnings.warn(f"{arch_fpath} already exists and will be overwritten.")
    output_dir.mkdir(parents=True, exist_ok=True)
    nhsn_df.to_csv(arch_fpath, index=False)
    print("Exporting done.")

    if save_latest:
        latest_fname = output_dir / f"nhsn_latest.csv"
        print(f"Exporting to {latest_fname}...")
        shutil.copy2(
            src=arch_fpath,
            dst=latest_fname,
        )
        print("Exporting done.")

    if update_metadata:
        # I'll write everything here because there are many arguments. Then I'll put in a function.
        entry = dict(
            filename=filename,
            fetched_on=now.isoformat(),
            data_updated_at=nhsn_metadata["dataUpdatedAt"],
            fetch_trigger=args.fetch_trigger,
            release=release,
            comments="",
        )

        # Update general fields
        dataset_metadata["last_updated"] = now.isoformat()

        print(f"Exporting metadata...")
        dataset_metadata["files"].append(entry)
        save_yaml(output_dir / "metadata.yaml", dataset_metadata)
        print("Exporting done.")


if __name__ == "__main__":
    main()

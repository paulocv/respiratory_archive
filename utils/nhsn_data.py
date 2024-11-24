"""
Python utilities to download hospital data of respiratory diseases
from the National Healthcare Safety Network (NHSN).

Contains a function to fetch data from the NHSN API (`fetch_nhsn_hosp_data`)
and a function to convert the fetched data into a hubverse-formatted
target DataFrame (`make_target_data_from_nhsn`).

The `fetch_nhsn_hosp_data` function requires a "locations" file or
DataFrame, with data from the US jurisdictions. Within this repository,
this file is at `aux_data/us_locations.csv`

If run as a script, it downloads the data and saves it to a CSV file. Example:
```bash
python fetch_data_utils.py --disease covid --locations-file aux_data/locations.csv
```

You can also import this module and call the functions directly.
```python
from fetch_data_utils import fetch_nhsn_hosp_data, make_target_data_from_nhsn

nhsn_df = fetch_nhsn_hosp_data()
truth_df = make_target_data_from_nhsn(nhsn_df, disease="covid")
```

Author: Paulo Cesar Ventura (https://github.com/paulocv, https://paulocv.netlify.app)

License: MIT
"""
import argparse
from pathlib import Path
from typing import Union
import requests

import pandas as pd


# --- Data URLs
_NHSN_DATA_REQUEST_FMT = "https://data.cdc.gov/resource/{uuid}.json"
_NHSN_METADATA_REQUEST_FMT = "https://data.cdc.gov/api/views/metadata/v1/{uuid}"
_UUID_CONSOLIDATED = "ua7e-t2fy"
_UUID_PRELIMINARY = "mpgq-jmmr"


def get_data_url(release):
    if release in ["prelim", "preliminary"]:
        return _NHSN_DATA_REQUEST_FMT.format(uuid=_UUID_PRELIMINARY)
    elif release in ["consol", "consolidated"]:
        return _NHSN_DATA_REQUEST_FMT.format(uuid=_UUID_CONSOLIDATED)
    else:
        raise ValueError(
            f"Unrecognized value for parameter `release`: {release}")


def get_metadata_url(release):
    if release in ["prelim", "preliminary"]:
        return _NHSN_METADATA_REQUEST_FMT.format(uuid=_UUID_PRELIMINARY)
    elif release in ["consol", "consolidated"]:
        return _NHSN_METADATA_REQUEST_FMT.format(uuid=_UUID_CONSOLIDATED)
    else:
        raise ValueError(
            f"Unrecognized value for parameter `release`: {release}")


# --- Conversion from disease names to NHSN new hosp. admission fields
_DISEASE_TO_NEWADM_FIELD = {
    "covid": "totalconfc19newadm",
    "covid19": "totalconfc19newadm",
    "covid-19": "totalconfc19newadm",
    "c19": "totalconfc19newadm",
    "influenza": "totalconfflunewadm",
    "flu": "totalconfflunewadm",
    "rsv": "totalconfrsvnewadm",
}

_INTEREST_NHSN_FIELDS = list()


# --- Fields to fetch from the NHSN dataset
# Admissions: TOTALS
_INTEREST_NHSN_FIELDS += [
  f"totalconf{disease}newadm{age}"
      for disease in ["c19", "flu", "rsv"]
      for age in ["", "adult", "ped"]
 ]

# Admissions: AGE GROUPS
_INTEREST_NHSN_FIELDS += [
  f"numconf{disease}newadm{age}"
      for disease in ["c19", "flu", "rsv"]
      for age in [
        "ped0to4", "ped5to17",   # Pediatric
        "adult18to49", "adult50to64", "adult65to74", "adult75plus",  # Adults
        "unk",   # Unknown age
    ]
]


def get_latest_nhsn_url() -> str:
    """Determines which release (preliminary or consolidated) of the
    NHSN data was updated most recently and returns its URL.
    """
    # Querry each dataset for the last updated date
    prelim_response = send_and_check_request(get_metadata_url("prelim"))
    prelim_json = prelim_response.json()
    prelim_date_str = prelim_json["dataUpdatedAt"]
    prelim_date = pd.Timestamp(prelim_date_str)

    consol_response = send_and_check_request(get_metadata_url("consol"))
    consol_json = consol_response.json()
    consol_date_str = consol_json["dataUpdatedAt"]
    consol_date = pd.Timestamp(consol_date_str)

    # Pick the latest, return the proper URL
    if prelim_date > consol_date:
        return get_data_url("preliminary")
    else:
        return get_data_url("consolidated")


def send_and_check_request(request_url, request_params=None) -> requests.Response:
    print(f"Requesting from {request_url}...")
    try:
        response = requests.get(request_url, params=request_params)
    except requests.exceptions.RequestException as err:
        raise Exception(
            f"An error ({err.__class__.__name__}) occurred during the request:\n{str(err)}"
        )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        raise requests.exceptions.HTTPError(
            f"An HTTP error occurred: {http_err}\n"
            f"Response content: {response.text}"
        )
    else:
        print("Request successful")

    return response


def fetch_nhsn_hosp_data(
        # as_of: Union[str, pd.Timestamp] = None,  # NHSN doesn't have data history
        # na_rm=False,
        request_url="https://data.cdc.gov/resource/ua7e-t2fy.json",
        entry_limit=100000,
        parse_dates=True,
        data_fields=None,
        start_date=None,  # TODO IMPLEMENT
) -> pd.DataFrame:
    """
    Fetch new hospitalization data from the NHSN (National Healthcare
    Safety Network) API.

    Parameters
    ----------
    request_url : str, optional
        URL to the NHSN API. Defaults to the URL of the "New Hospitalizations"
        dataset.
    entry_limit : int, optional
        Maximum number of entries to return. Defaults to 100000.
    parse_dates : bool
        Whether to parse date columns as pandas datetime entries.
    data_fields : list, optional
        A list of fields from the NHSN data to fetch, each one
        specified as a string with the API Field Name. Defaults to the
        `_interest_nhsn_fields` variable.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the new hospitalizations data.

    Notes
    -----
    The NHSN API does not provide access to historical data. Therefore, the
    `as_of` parameter is not implemented.
    """
    data_fields = data_fields or _INTEREST_NHSN_FIELDS

    # Build request options
    # ========================
    request_fields = [
        "weekendingdate", "jurisdiction",  # Date, location
        # # --- New hospitalizations
        # "totalconfflunewadm",  # New hospitalizations by flu
        # "totalconfc19newadm",  # New hospitalizations by Covid-19
        # "totalconfrsvnewadm",  # New hospitalizations by RSV
    ]

    request_fields += data_fields  # Hospital data fields

    request_params = {
        "$limit": entry_limit,
        "$select": ",".join(request_fields)
    }

    # Send request to the API
    # ========================
    response = send_and_check_request(request_url, request_params)
    # print(f"Requesting from {request_url}...")
    # try:
    #     response = requests.get(request_url, params=request_params)
    # except requests.exceptions.RequestException as err:
    #     raise Exception(
    #         f"An error ({err.__class__.__name__}) occurred during the request:\n{str(err)}"
    #     )
    #
    # try:
    #     response.raise_for_status()
    # except requests.exceptions.HTTPError as http_err:
    #     raise requests.exceptions.HTTPError(
    #         f"An HTTP error occurred: {http_err}\n"
    #         f"Response content: {response.text}"
    #     )
    # else:
    #     print("Request successful")
    #

    # PARSE THE RESPONSE
    # ==================
    print("Parsing response as a data frame...")
    nhsn_df = pd.DataFrame.from_records(response.json())

    if parse_dates:
        nhsn_df["weekendingdate"] = pd.to_datetime(nhsn_df["weekendingdate"])

    return nhsn_df


def make_target_data_from_nhsn(
        nhsn_df, disease="covid",
        locations_data: Union[str, pd.DataFrame] = "aux_data/us_locations.csv"
) -> pd.DataFrame:
    """Create a hubverse-formatted target data from a fetched NHSN data frame.

    The returned data frame has columns "date", "location", "location_name",
    "value" and "weekly_rate".

    Parameters
    ----------
    nhsn_df : pd.DataFrame
        A data frame with the fetched NHSN data.
    disease : str
        The disease to be used to select the target data. The following
        values are admissible: "covid", "covid19", "covid-19", "c19",
        "influenza", "flu", "rsv".
    locations_data : Union[str, pd.DataFrame]
        A path to the locations.csv file or a loaded data frame. If
        not informed, it defaults to "aux_data/us_locations.csv".

    Returns
    -------
    pd.DataFrame
        A data frame with the target data in the hubverse format.
    """
    print(f"Preparing the target data for disease: {disease}...")
    # Preprocess arguments
    # ====================

    # --- Load locations data
    if isinstance(locations_data, (str, Path)):
        # Informed as a path to the locations.csv file
        locations_df = pd.read_csv(locations_data)
    elif isinstance(locations_data, pd.DataFrame):
        # Informed directly as a dataframe
        locations_df = locations_data.copy()
    else:
        raise TypeError(
            "Parameter `locations_data` must either be a pandas data frame"
            f" or a path to the locations file, but a {type(locations_data)} "
            f"was given.")

    # --- Disease name to its NHSN fields
    try:
        disease_nhsn_field = _DISEASE_TO_NEWADM_FIELD[disease.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown value of parameter `disease` = \"{disease}\". "
            f"Must be one of the following: "
            f"{list(_DISEASE_TO_NEWADM_FIELD.keys())}"
        )
    except AttributeError:
        raise TypeError(
            f"Parameter `disease` does not have `lower()` method. "
            f"Must be a string, but a {type(disease)} "
            f"was given.")

    # Generate the hubverse formatted truth/target dataframe
    # ===========
    # Select fields of interest and copy from the original data frame
    fields = [
        "weekendingdate", "jurisdiction", disease_nhsn_field
    ]
    df = nhsn_df[fields].copy()

    # Convert some data types
    df["weekendingdate"] = pd.to_datetime(df["weekendingdate"])
    df[disease_nhsn_field] = pd.to_numeric(df[disease_nhsn_field])

    # Convert USA to US, to match the `location` field in locations.csv
    df.loc[df['jurisdiction'] == 'USA', 'jurisdiction'] = 'US'

    # Filter jurisdictions that are not in the locations data (warn if any)
    mask = df["jurisdiction"].isin(locations_df["abbreviation"])
    if not mask.all():
        diff = df["jurisdiction"].loc[~mask].unique()
        print(
            f"Warning: {len(diff)} jurisdictions from the NHSN data were "
            f"not found in the locations data: {diff}. They will be "
            f"ignored.")
    df = df[mask]

    # Get jurisdiction full name and fips code
    index_df = locations_df.set_index("abbreviation")
    df["location"] = df["jurisdiction"].map(lambda x: index_df.loc[x, "location"])
    df["location_name"] = df["jurisdiction"].map(lambda x: index_df.loc[x, "location_name"])

    # Rename some columns
    df = df.rename(columns={
        "weekendingdate": "date",
        disease_nhsn_field: "value",
    })

    # Add weekly rate (by 100k inhabitants)
    df["population"] = df["jurisdiction"].map(lambda x: index_df.loc[x, "population"])
    df["weekly_rate"] = df["value"] / df["population"] * 1E5

    # Drop columns and sort them as in the target data file
    # df = df.drop(columns=["jurisdiction"])
    df = df[["date", "location", "location_name", "value", "weekly_rate"]]

    # Sort rows by date and location
    df = df.sort_values(["date", "location"])

    return df


# ==========================================================


if __name__ == "__main__":

    # --- Fetch NHSN data and save into files

    def parse_args():
        parser = argparse.ArgumentParser(
            usage="Fetch Weekly Hospital Respiratory Data from the "
                  "National Healthcare Safety Network (NHSN).",
        )
        parser.add_argument(
            "--disease",
            type=str,
            help="Disease for which the target data is constructed. "
                 f"Values: {list(_DISEASE_TO_NEWADM_FIELD.keys())}",
            default="flu"
        )

        parser.add_argument(
            "--preliminary",
            type=bool,
            help="Whether to use the preliminary NHSN data instead of the "
                 "consolidated one. The preliminary data is released on"
                 "the Wednsesday before the conosolidate data. While "
                 "incomplete, it provides earlier access to the latest "
                 "week data.",
            default=True,
            action=argparse.BooleanOptionalAction,
        )

        parser.add_argument(
            "--locations-file",
            type=Path,
            help="Path to the input locations file, containing information"
                 " about the US jurisdictions.",
            default="aux_data/us_locations.csv",
        )

        parser.add_argument(
            "--entry-limit", "--limit", "-l",
            type=int,
            help="Limit to the number of entries (rows) fetched from the "
                 "NHSN API. Use lower values to reduce the load (e.g. for"
                 " debugging purposes). Use larger values if the dataset"
                 " is larger than the default value.",
            default=100000,
        )

        parser.add_argument(
            "--export-truth", "--export-target",
            type=bool,
            action=argparse.BooleanOptionalAction,
            help="Whether to export the target data into a file.",
            default=True,
        )

        parser.add_argument(
            "--truth-file", "--target-file",
            type=Path,
            help="File path to save the truth/target data file on.",
            default="hosp_data/truth_latest.csv",
        )

        parser.add_argument(
            "--export-nhsn",
            type=bool,
            action=argparse.BooleanOptionalAction,
            help="Whether to export the fetched NHSN data into a file.",
            default=True,
        )

        parser.add_argument(
            "--nhsn-file",
            type=Path,
            help="File path to save the NHSN data file on.",
            default="hosp_data/NHSN/nhsn_hosp_latest.csv",
        )

        return parser.parse_args()


    def main():
        args = parse_args()

        if args.preliminary:
            url = "https://data.cdc.gov/resource/mpgq-jmmr.json"
        else:
            url = "https://data.cdc.gov/resource/ua7e-t2fy.json"

        # nhsn_df = fetch_nhsn_hosp_data(entry_limit=100)  # Lightweight fetch, for debugging
        nhsn_df = fetch_nhsn_hosp_data(
            entry_limit=args.entry_limit, request_url=url
        )

        if args.export_nhsn:
            fpath: Path = args.nhsn_file
            print(f"Exporting NHSN data to {fpath}...")
            fpath.parent.mkdir(parents=True, exist_ok=True)
            nhsn_df.to_csv(fpath, index=False)

        return

    main()

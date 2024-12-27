"""
Create plots from the NHSN dataset, for selectable diseases and
jurisdictions. Shows the time series as of each report date.

Concepts:
- as_of_date: Date and time in which the dataset was updated. "As of" date.
- date: Date of the report, attributed to the hospitalization event.
"""
import logging
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import jinja2
import numpy as np
import pandas as pd
import plotly
import plotly.graph_objects as go
import plotly.express as px

from utils.nhsn_data import DISEASE_CODE3_TO_NAME
from utils.yaml_tools import load_yaml


_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)
_LOGGER.addHandler(logging.StreamHandler(sys.stdout))


def main():
    params = Params()
    data = Data()

    load_data(params, data)
    prepare_plots(params, data)
    fill_templates(params, data)
    export_all(params, data)


class Params:
    templates_dir: Path
    dataset_dir: Path

    def __init__(self):
        # Respiratory dataset
        self.dataset_dir = Path("./datasets/nhsn_weekly_jurisdiction")
        self.dataset_metadata_fname: str = "metadata.yaml"
        self.minimum_as_of_date: pd.Timestamp = pd.Timestamp("2024-12-04")
        self.date_colname: str = "weekendingdate"
        self.jurisdiction_colname: str = "jurisdiction"
        self.hosp_colname_fmt: str = "totalconf{}newadm"
        #   ^ ^  Formats by the 3-letter disease code: c19, flu, rsv

        # Plot options – Hospitalizations time series
        self.show_default_jurisd: str = "USA"  # Jurisdiction to show when plots are created
        self.plot_date_lim_left: pd.Timestamp = pd.Timestamp.now() - pd.Timedelta("15w")# Timestamp("2024-01-01")  # Earliest date to show on plots' default view
        # self.plot_date_lim_left: pd.Timestamp = pd.Timestamp("2024-01-01")  # Earliest date to show on plots' default view

        # HTML page and templates
        self.templates_dir = Path("./html_templates")
        self.pages_build_dir = Path("./pages")

        # Misc
        self.locations_path = Path("./aux_data/us_locations.csv")


class Data:
    locations_df: pd.DataFrame

    main_archive_df: pd.DataFrame  # Big data frame with all NHSN archived data
    dataset_metadata_dict: dict    # Contents of NHSN metadata YAML file

    template_fill_dict: dict  # Contents that will fill the templates
    index_page_content: str   # HTML content for the index page

    def __init__(self):
        self.template_fill_dict = dict()


def parse_args():
    pass


def load_data(params: Params, data: Data):

    # Load locations data
    # ============
    data.locations_df = pd.read_csv(params.locations_path)

    # Load dataset metadata
    # ============
    dataset_metadata_path = params.dataset_dir / params.dataset_metadata_fname
    data.dataset_metadata_dict = load_yaml(dataset_metadata_path)

    # Load each file in the dataset
    # ============
    df_list = list()
    key_list = list()
    for file_entry in data.dataset_metadata_dict["files"]:

        # Preprocess (CHANGES INPLACE) the file metadata
        file_path = params.dataset_dir / file_entry["filename"]

        # --- Convert to pandas datetime and EST timezone
        file_entry["data_updated_at"] = pd.Timestamp(file_entry["data_updated_at"])
        if file_entry["data_updated_at"].tzinfo is not None:
            file_entry["data_updated_at"] = file_entry["data_updated_at"].astimezone("US/Eastern").replace(tzinfo=None)

        # Filters
        # =======
        if not file_path.exists():
            _LOGGER.warning(f"File {file_path} does not exist. Skipping.")
            continue

        if file_entry["data_updated_at"] < params.minimum_as_of_date:
            _LOGGER.info(f"Dataset on {file_path} is before minimmum date. Skipping.")
            continue

        # Loading
        # ======
        _LOGGER.debug(f"Loading {file_entry['filename']}")

        try:
            df = pd.read_csv(
                file_path, parse_dates=[params.date_colname],
                index_col=[params.date_colname, params.jurisdiction_colname],
            )
        except pd.errors.ParserError:
            _LOGGER.error(f"File {file_path} could not be parsed. Skipping.")
            continue

        date = pd.Timestamp(file_entry["data_updated_at"].date())  # Retain the date only, reset hour
        if date in key_list:
            _LOGGER.warning(f"Duplicate date {date} in file {file_path}. Skipping.")
            continue

        _LOGGER.info(f"Loaded {file_entry['filename']}")
        df_list.append(df)
        key_list.append(date)

    if len(df_list) == 0:
        _LOGGER.error("No files loaded. Exiting.")
        exit(1)

    data.main_archive_df = pd.concat(
        df_list, ignore_index=False,
        keys=key_list,
        names=["as_of_date"],
        axis=0,
    )


def prepare_plots(params: Params, data: Data):

    # --- Initialize plots and surrounding data
    disease_codes = ["c19", "flu", "rsv"]
    fig_dict = {code: go.Figure() for code in disease_codes}

    num_jurisdictions = len(data.main_archive_df.index.get_level_values("jurisdiction").unique())

    # Plot data
    # ===================

    # --- Loop over jurisdictions
    i_trace = 0
    jur_trace_indices = defaultdict(list)  # Keeps track of the trace indices belonging to each jurisdiction
    for i_jur, (jur_abbrev, jur_df) in (
            enumerate(data.main_archive_df.groupby(by="jurisdiction", group_keys=False))):
        jur_df = jur_df.droplevel("jurisdiction")
        # Jurisdiction visible by default
        start_visible = (jur_abbrev == params.show_default_jurisd)

        # Report progress
        if i_jur % 10 == 0:
            _LOGGER.info(f"Processing jurisdiction {jur_abbrev} ({i_jur} / {num_jurisdictions})")

        # --- Loop over as-of dates
        for i_as_of, (as_of_date, as_of_df) in (
                enumerate(jur_df.groupby(
                    by="as_of_date", group_keys=False, sort=True,
                ))):
            as_of_df = as_of_df.droplevel("as_of_date")

            # --- Loop over diseases
            for disease_code in disease_codes:
                # disease_name = DISEASE_CODE3_TO_NAME[disease_code]
                hosp_colname = params.hosp_colname_fmt.format(disease_code)
                fig = fig_dict[disease_code]

                plot_sr = as_of_df[hosp_colname].sort_index()
                fig.add_scatter(
                    x=plot_sr.index,
                    y=plot_sr,
                    name=as_of_date.date().isoformat(),
                    visible=start_visible,
                    zorder=-i_as_of,
                )

            # Track the traces belonging to this jurisdiction
            jur_trace_indices[jur_abbrev].append(i_trace)
            i_trace += 1

    # Configure plots
    # ===================
    _LOGGER.info("Configuring plots")
    num_traces = i_trace

    # --- Loop over jurisdictions to build its dropdown
    jur_buttons = list()
    for i_jur, (jur_abbrev, trace_indices) in enumerate(jur_trace_indices.items()):
        # Define the button, set all traces as invisible
        button = dict(
            label=jur_abbrev,
            method="update",
            args=[{"visible": np.zeros(num_traces, dtype=bool)}],
        )
        # Set selected traces as visible
        button["args"][0]["visible"][trace_indices] = True

        # Store, ensuring the default comes first
        if jur_abbrev == params.show_default_jurisd:
            jur_buttons.insert(0, button)
        else:
            jur_buttons.append(button)

    # --- Setup selection dropdowns
    for fig in fig_dict.values():
        fig.update_layout(
            updatemenus=[
                # --- Jurisdiction selection
                dict(
                    buttons=jur_buttons,
                    name="Jurisdiction"
                )
            ],
        )

    # --- Setup other options
    max_date = data.main_archive_df.index.get_level_values("weekendingdate").max()
    for fig in fig_dict.values():
        fig.update_xaxes(
            range=[params.plot_date_lim_left, max_date],
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                y=1.2
            ),
            margin=dict(l=0, r=0, t=90, b=40),
            autosize=False,
            minreducedwidth=400,
            width=800,
            paper_bgcolor="hsla(187, 36%, 95%, 0)",
            # plot_bgcolor="hsl(187, 36%, 95%)",
        )
        fig.update_xaxes(automargin=True)
        fig.update_yaxes(automargin=True)

    # Export figure HTML into the template filling contents
    # ==============
    for code, fig in fig_dict.items():
        data.template_fill_dict[f"{code}_plot"] = fig.to_html(full_html=False, include_plotlyjs=False)


def fill_templates(params: Params, data: Data):
    _LOGGER.info("Filling templates")

    # Fill other metadata
    # =============
    data.template_fill_dict["report_date"] = pd.Timestamp.now().date().isoformat()


    # ===============

    _LOGGER.info(f"Loading templates from directory: {params.templates_dir}")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(params.templates_dir))

    template = env.get_template("simple_report.html")
    data.index_page_content = template.render(**data.template_fill_dict)


    # # TESTTTTTT : Export to this wrong place
    # with open(params.templates_dir / "index.html", "w") as f:
    #     f.write(page_content)
    # pass


def export_all(params: Params, data: Data):
    _LOGGER.info("Exporting site files")

    # --- Check and warn about content overwriting
    if not params.pages_build_dir.is_dir() or not any(params.pages_build_dir.iterdir()):
        _LOGGER.debug(f"Export directory is empty: {params.pages_build_dir}")
    else:
        _LOGGER.warning(f"Export directory is not empty. Files will be overwritten: {params.pages_build_dir}")
        # --- Clear the export directory
        for f in params.pages_build_dir.iterdir():
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)

    # --- Copy relevant files
    files_to_copy = [
        params.templates_dir / "simple_report_style.css",
        params.templates_dir / "simple_report_scripts.js",
    ]
    for f in files_to_copy:
        shutil.copy(f, params.pages_build_dir)

    # --- Export filled template
    with open(params.pages_build_dir / "index.html", "w") as fp:
        fp.write(data.index_page_content)

    _LOGGER.info("Exports completed")


if __name__ == "__main__":
    main()

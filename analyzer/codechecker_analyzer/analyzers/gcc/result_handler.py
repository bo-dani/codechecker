# -------------------------------------------------------------------------
#
#  Part of the CodeChecker project, under the Apache License v2.0 with
#  LLVM Exceptions. See LICENSE for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# -------------------------------------------------------------------------
"""
Result handler for Gcc.
"""
from typing import Optional
from pathlib import Path
import shutil
import os

from codechecker_report_converter.report.parser.base import AnalyzerInfo
from codechecker_report_converter.analyzers.gcc.analyzer_result import \
    AnalyzerResult
from codechecker_report_converter.report import report_file
from codechecker_report_converter.report.hash import get_report_hash, HashType

from codechecker_common.logger import get_logger
from codechecker_common.skiplist_handler import SkipListHandlers

from ..result_handler_base import ResultHandler

LOG = get_logger('analyzer.gcc')


def actual_name_to_codechecker_name(actual_name: str):
    assert actual_name.startswith('-Wanalyzer')
    return actual_name.replace("-Wanalyzer", "gcc")


def codechecker_name_to_actual_name(codechecker_name: str):
    assert codechecker_name.startswith('gcc')
    return codechecker_name.replace("gcc", "-Wanalyzer")


def codechecker_name_to_actual_name_disabled(codechecker_name: str):
    assert codechecker_name.startswith('gcc')
    return codechecker_name.replace("gcc", "-Wno-analyzer")


class GccResultHandler(ResultHandler):
    """
    Create analyzer result file for Gcc output.
    """

    def __init__(self, *args, **kwargs):
        self.analyzer_info = AnalyzerInfo(name=AnalyzerResult.TOOL_NAME)
        self.gcc_analyzer_result = AnalyzerResult()

        super(GccResultHandler, self).__init__(*args, **kwargs)

    def postprocess_result(self, skip_handlers: Optional[SkipListHandlers]):
        """
        Generate analyzer result output file which can be parsed and stored
        into the database.
        """
        LOG.debug_analyzer(self.analyzer_stdout)

        # GCC places sarif files to the "directory" entry found in the
        # compilation database. As of writing this comment, there is no way to
        # tell GCC to place is elsewhere, so we need to find it, move it and
        # rename it.
        file_name = os.path.basename(self.analyzed_source_file)
        gcc_output_file = \
                str(Path(self.buildaction.directory, file_name)) + ".sarif"

        assert os.path.exists(gcc_output_file), \
                "Faile to find the sarif file for GCC analysis!"

        reports = report_file.get_reports(
            gcc_output_file, self.checker_labels,
            source_dir_path=self.source_dir_path)

        # FIXME: We absolutely want to support gcc compiler warnings
        # eventually (which don't start with '-Wanalyzer'), but we should
        # probably list them in the label files as well, etc.
        reports = \
            [r for r in reports if not r.skip(skip_handlers) and
             r.checker_name.startswith("-Wanalyzer")]

        for report in reports:
            report.checker_name = \
                actual_name_to_codechecker_name(report.checker_name)

        hash_type = HashType.PATH_SENSITIVE
        if self.report_hash_type == 'context-free-v2':
            hash_type = HashType.CONTEXT_FREE
        elif self.report_hash_type == 'diagnostic-message':
            hash_type = HashType.DIAGNOSTIC_MESSAGE

        for report in reports:
            report.report_hash = get_report_hash(report, hash_type)

        report_file.create(
            self.analyzer_result_file, reports, self.checker_labels,
            self.analyzer_info)

        # TODO Maybe move this to post_analyze?
        gcc_out_folder = Path(self.workspace, "gcc")
        gcc_out_folder.mkdir(exist_ok=True)
        gcc_dest_file_name = \
            Path(gcc_out_folder, os.path.basename(self.analyzed_source_file) +
                 self.buildaction_hash + ".sarif.bak")
        try:
            shutil.move(gcc_output_file, gcc_dest_file_name)
        except(OSError) as e:
            LOG.error(f"Failed to move '{gcc_output_file}' to "
                      f"'{gcc_out_folder}': {e}")

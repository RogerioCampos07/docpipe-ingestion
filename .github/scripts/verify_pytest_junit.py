"""Fail CI when a pytest phase is empty, skipped, or incomplete."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


def _expectation(value: str) -> tuple[str, int]:
    module, separator, minimum = value.rpartition('=')
    if not separator or not module:
        raise argparse.ArgumentTypeError(
            'expected MODULE=MINIMUM, for example tests.integration.test=1'
        )
    try:
        count = int(minimum)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            'MINIMUM must be an integer'
        ) from error
    if count < 1:
        raise argparse.ArgumentTypeError('MINIMUM must be positive')
    return module, count


def verify(
    report: Path,
    requirements: list[tuple[str, int]],
) -> None:
    if not report.is_file():
        raise ValueError(f'pytest report does not exist: {report}')

    root = ElementTree.parse(report).getroot()
    testcases = root.findall('.//testcase')
    if not testcases:
        raise ValueError(f'pytest report contains no test cases: {report}')

    failures = root.findall('.//failure')
    errors = root.findall('.//error')
    skipped = root.findall('.//skipped')
    if failures or errors or skipped:
        raise ValueError(
            f'pytest report is not clean: failures={len(failures)}, '
            f'errors={len(errors)}, skipped={len(skipped)}'
        )

    modules = Counter(
        case.attrib.get('classname', '').removesuffix(
            f'.{case.attrib.get("name", "")}'
        )
        for case in testcases
    )
    missing = [
        f'{module} ({modules[module]}/{minimum})'
        for module, minimum in requirements
        if modules[module] < minimum
    ]
    if missing:
        raise ValueError(
            'pytest report is missing required tests: ' + ', '.join(missing)
        )

    print(f'verified {len(testcases)} executed tests in {report}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument(
        '--require-module',
        action='append',
        default=[],
        type=_expectation,
        metavar='MODULE=MINIMUM',
    )
    arguments = parser.parse_args()
    verify(arguments.report, arguments.require_module)


if __name__ == '__main__':
    main()

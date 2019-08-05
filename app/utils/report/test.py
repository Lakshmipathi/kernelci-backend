# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Create the tests email report."""

import models
import pymongo
import utils
import os
import utils.db
import utils.report.common as rcommon

TEST_REPORT_FIELDS = [
    models.ARCHITECTURE_KEY,
    models.BOARD_INSTANCE_KEY,
    models.BOARD_KEY,
    models.BOOT_ID_KEY,
    models.BOOT_LOG_HTML_KEY,
    models.BOOT_LOG_KEY,
    models.BUILD_ID_KEY,
    models.BUILD_ENVIRONMENT_KEY,
    models.COMPILER_VERSION_FULL_KEY,
    models.CREATED_KEY,
    models.DEFCONFIG_FULL_KEY,
    models.DEFCONFIG_KEY,
    models.DEFINITION_URI_KEY,
    models.DEVICE_TYPE_KEY,
    models.GIT_BRANCH_KEY,
    models.GIT_COMMIT_KEY,
    models.GIT_DESCRIBE_KEY,
    models.GIT_URL_KEY,
    models.ID_KEY,
    models.INITRD_KEY,
    models.INITRD_INFO_KEY,
    models.JOB_ID_KEY,
    models.JOB_KEY,
    models.KERNEL_KEY,
    models.LAB_NAME_KEY,
    models.METADATA_KEY,
    models.NAME_KEY,
    models.STATUS_KEY,
    models.TEST_CASES_KEY,
    models.SUB_GROUPS_KEY,
    models.TIME_KEY,
    models.VCS_COMMIT_KEY,
    models.VERSION_KEY,
]

# FIXME: get this from test-configs.yaml
TEST_PLAN_OPTIONS = {
    "v4l2-compliance-uvc": {
        "subject": "v4l2-compliance on uvcvideo",
        "template": "plans/v4l2-compliance.txt",
        "params": {
            "driver_name": "uvcvideo",
        },
    },
    "v4l2-compliance-vivid": {
        "subject": "v4l2-compliance on vivid",
        "template": "plans/v4l2-compliance.txt",
        "params": {
            "driver_name": "vivid",
        },
    },
}


def _regression_message(data):
    last_pass = data[0]
    first_fail = data[1]
    last_fail = data[-1]

    if len(data) == 2:
        return "new failure (last pass: {})".format(
            last_pass[models.KERNEL_KEY])

    delta = last_fail[models.CREATED_KEY] - first_fail[models.CREATED_KEY]
    plural = 's' if delta.days > 1 else ''
    return "failing since {} day{} (last pass: {}, first fail: {})".format(
        delta.days, plural, last_pass[models.KERNEL_KEY],
        first_fail[models.KERNEL_KEY])


def _add_test_group_data(group, db, spec, hierarchy=[]):
    hierarchy = hierarchy + [group[models.NAME_KEY]]
    case_collection = db[models.TEST_CASE_COLLECTION]
    regr_collection = db[models.TEST_REGRESSION_COLLECTION]
    group_collection = db[models.TEST_GROUP_COLLECTION]
    regr_spec = dict(spec)
    regr_count = 0

    test_cases = []
    for test_case_id in group[models.TEST_CASES_KEY]:
        test_case = utils.db.find_one2(case_collection, test_case_id)
        if test_case[models.STATUS_KEY] == "FAIL":
            regr_spec[models.HIERARCHY_KEY] = (
                hierarchy + [test_case[models.NAME_KEY]])
            regr = utils.db.find_one2(regr_collection, regr_spec)
            test_case["failure_message"] = (
                _regression_message(regr[models.REGRESSIONS_KEY])
                if regr else "never passed")
            if regr:
                regr_count += 1
        test_cases.append(test_case)

    test_cases.sort(key=lambda tc: tc[models.INDEX_KEY])

    sub_groups = []
    for sub_group_id in group[models.SUB_GROUPS_KEY]:
        sub_group = utils.db.find_one2(group_collection, sub_group_id)
        _add_test_group_data(sub_group, db, spec, hierarchy)
        sub_groups.append(sub_group)

    results = {
        st: len(list(t for t in test_cases if t[models.STATUS_KEY] == st))
        for st in ["PASS", "FAIL", "SKIP"]
    }

    total_results = dict(results)

    for sub_group_sums in (sg["total_results"] for sg in sub_groups):
        for status, count in sub_group_sums.iteritems():
            total_results[status] += count

    total_regr = regr_count + sum(sg["regr_count"] for sg in sub_groups)

    group.update({
        "test_cases": test_cases,
        "results": results,
        "regr_count": regr_count,
        "sub_groups": sub_groups,
        "total_regr": total_regr,
        "total_tests": sum(total_results.values()),
        "total_results": total_results,
    })


def create_test_report(data, email_format, email_template, db_options,
                       base_path=utils.BASE_PATH):
    """Create the tests report email to be sent.

    :param data: The meta-data for the test job.
    :type data: dictionary
    :param email_format: The email format to send.
    :type email_format: list
    :param email_template: The email template to use send.
    :type email_template: str
    :param db_options: The mongodb database connection parameters.
    :type db_options: dict
    :param base_path: Path to the top-level storage directory.
    :type base_path: string
    :return A tuple with the email body, the email subject and the headers as
    dictionary.  If an error occured, None.
    """
    database = utils.db.get_db_connection(db_options)

    job, branch, kernel, plan = (data[k] for k in [
        models.JOB_KEY,
        models.GIT_BRANCH_KEY,
        models.KERNEL_KEY,
        models.PLAN_KEY,
    ])

    plan_options = TEST_PLAN_OPTIONS.get(plan, {})

    spec = {x: y for x, y in data.iteritems() if x != models.PLAN_KEY}
    group_spec = dict(spec)
    group_spec.update({
        models.NAME_KEY: plan,
        models.PARENT_ID_KEY: None,
    })

    groups = list(utils.db.find(
        database[models.TEST_GROUP_COLLECTION],
        spec=group_spec,
        fields=TEST_REPORT_FIELDS,
        sort=[
            (models.BOARD_KEY, pymongo.ASCENDING),
            (models.BUILD_ENVIRONMENT_KEY, pymongo.ASCENDING),
            (models.DEFCONFIG_KEY, pymongo.ASCENDING),
            (models.LAB_NAME_KEY, pymongo.ASCENDING),
            (models.ARCHITECTURE_KEY, pymongo.ASCENDING),
        ])
    )

    if not groups:
        utils.LOG.warning("Failed to find test group documents")
        return None

    for group in groups:
        group_spec = dict(spec)
        group_spec.update({
            k: group[k] for k in [
                models.DEVICE_TYPE_KEY,
                models.ARCHITECTURE_KEY,
                models.BUILD_ENVIRONMENT_KEY,
                models.DEFCONFIG_FULL_KEY,
            ]
        })
        _add_test_group_data(group, database, group_spec)

    tests_total = sum(group["total_tests"] for group in groups)
    regr_total = sum(group["total_regr"] for group in groups)

    plan_subject = plan_options.get("subject", plan)
    subject_str = "{}/{} {}: {} runs, {} regressions ({})".format(
        job, branch, plan_subject, len(groups), regr_total, kernel)

    git_url, git_commit = (groups[0][k] for k in [
        models.GIT_URL_KEY, models.GIT_COMMIT_KEY])

    # Add test suites info if it's the same for all the groups (typical case)
    keys = set()
    last_test_suites = None
    for g in groups:
        info = g[models.INITRD_INFO_KEY]
        if not info:
            continue
        last_test_suites = info.get('tests_suites')
        if not last_test_suites:
            continue
        keys.add(tuple(
            (ts['name'], ts['git_commit']) for ts in last_test_suites)
        )

    test_suites = list(last_test_suites) if len(keys) == 1 else None

    totals = {
        status: sum(g['total_results'][status] for g in groups)
        for status in ["PASS", "FAIL", "SKIP"]
    }

    headers = {
        rcommon.X_REPORT: rcommon.TEST_REPORT_TYPE,
        rcommon.X_BRANCH: branch,
        rcommon.X_TREE: job,
        rcommon.X_KERNEL: kernel,
    }

    template_data = {
        "subject_str": subject_str,
        "tree": job,
        "branch": branch,
        "git_url": git_url,
        "kernel": kernel,
        "git_commit": git_commit,
        "plan": plan,
        "boot_log": models.BOOT_LOG_KEY,
        "boot_log_html": models.BOOT_LOG_HTML_KEY,
        "storage_url": rcommon.DEFAULT_STORAGE_URL,
        "test_groups": groups,
        "test_suites": test_suites,
        "totals": totals,
    }

    if email_template:
        path = os.getcwd() + "/utils/report/templates"
        templates = [t for t in os.listdir(path)]
        template_file = str(email_template) + ".txt"
        if template_file in templates:
            template = template_file
        else:
            utils.LOG.warning("Email template not found: {}".format(
                template_file))
            return None
    else:
        template = "test.txt"

    template_data.update(plan_options.get("params", {}))
    body = rcommon.create_txt_email(template, **template_data)

    return body, subject_str, headers

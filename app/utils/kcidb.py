# Copyright (C) Collabora Limited 2019
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Push data using kcidb-submit."""

import json
import os
import subprocess

import models
import utils
import utils.db

# To print some noisy debug stuff in the log
debug = True


# Mapping between kcidb revision keys and build documents
BUILD_REV_KEY_MAP = {
    'git_repository_url': models.GIT_URL_KEY,
    'git_repository_commit_hash': models.GIT_COMMIT_KEY,
    'git_repository_commit_name': models.GIT_DESCRIBE_V_KEY,
    'git_repository_branch': models.GIT_BRANCH_KEY,
}


def _make_id(raw_id, ns):
    return ':'.join([ns, str(raw_id)])


def _get_build_doc(group, db):
    keys = [
        models.JOB_KEY,
        models.KERNEL_KEY,
        models.GIT_BRANCH_KEY,
        models.ARCHITECTURE_KEY,
        models.DEFCONFIG_KEY,
        models.BUILD_ENVIRONMENT_KEY,
    ]
    spec = {k: group[k] for k in keys}

    return utils.db.find_one2(db[models.BUILD_COLLECTION], spec)


def _get_test_cases(group, db, hierarchy, ns):
    case_collection = db[models.TEST_CASE_COLLECTION]
    group_collection = db[models.TEST_GROUP_COLLECTION]

    hierarchy = hierarchy + [group[models.NAME_KEY]]
    tests = [
        {
            'id': _make_id(test[models.ID_KEY], ns),
            'path': '.'.join(hierarchy + [test[models.NAME_KEY]]),
            'status': test[models.STATUS_KEY],
        }
        for test in (
            utils.db.find_one2(case_collection, test_id)
            for test_id in group[models.TEST_CASES_KEY]
        )
    ]

    for sub_group_id in group[models.SUB_GROUPS_KEY]:
        sub_group = utils.db.find_one2(group_collection, sub_group_id)
        tests += _get_test_cases(sub_group, db, hierarchy, ns)

    return tests


def _submit(data, bq_options):
    json_data = json.dumps(data, indent=2)
    print("submitting:")  # debug
    print(json_data)
    local_env = dict(os.environ)
    local_env["GOOGLE_APPLICATION_CREDENTIALS"] = bq_options["credentials"]
    kcidb_path = bq_options.get("kcidb_path", "")
    kcidb_submit = os.path.join(kcidb_path, "kcidb-submit")
    p = subprocess.Popen([kcidb_submit, "-d", bq_options["dataset"]],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         env=local_env)
    p.communicate(input=json_data)
    if p.returncode:
        print("WARNING: Failed to push data to BigQuery")


def push_build(build_id, first, bq_options, db_options={}, db=None):
    global debug
    if debug:
        print("BigQuery options:")
        for k, v in bq_options.iteritems():
            print("{:16} {}".format(k, v))
        debug = False
    print("first: {}".format(first))
    if db is None:
        db = utils.db.get_db_connection(db_options)
    origin = bq_options.get("origin", "kernelci")
    ns = bq_options.get("namespace", "kernelci.org")
    build = utils.db.find_one2(db[models.BUILD_COLLECTION], build_id)
    build_id = _make_id(build[models.ID_KEY], ns)
    revision_id = _make_id(build[models.KERNEL_KEY], ns)

    data = {
        'version': '1',
    }

    if first:
        revision = {
            'origin': origin,
            'origin_id': revision_id,
        }
        revision.update({
            rev_key: build[build_key]
            for rev_key, build_key in BUILD_REV_KEY_MAP.iteritems()
        })
        data['revisions'] = [revision]

    data['builds'] = [
        {
            'revision_origin': origin,
            'revision_origin_id': revision_id,
            'origin': origin,
            'origin_id': build_id,
        },
    ]

    _submit(data, bq_options)


def push_tests(group_id, bq_options, db_options={}, db=None):
    if db is None:
        db = utils.db.get_db_connection(db_options)
    collection = db[models.TEST_GROUP_COLLECTION]
    group = utils.db.find_one2(collection, group_id)
    origin = bq_options.get("origin", "kernelci")
    ns = bq_options.get("namespace", "kernelci.org")
    test_cases = _get_test_cases(group, db, [], ns)
    build = _get_build_doc(group, db)
    build_id = _make_id(build[models.ID_KEY], ns)

    data = {
        'version': '1',
        "tests": [
            {
                'build_origin': origin,
                'build_origin_id': build_id,
                'origin': origin,
                'origin_id': test['id'],
                'path': test['path'],
                'status': test['status'],
            }
            for test in test_cases
        ],
    }
    _submit(data, bq_options)

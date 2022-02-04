# SPDX-FileCopyrightText: 2019 Tomas Bellus
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# -*- coding: utf-8 -*-
"""
Testing Github API Collectors
"""
from cgitb import text
import json
import os
from unittest import TestCase, main as unittest_main
import requests_mock

import intelmq.lib.exceptions as exceptions
import intelmq.lib.test as test
import intelmq.lib.utils as utils
from intelmq.bots.collectors.github_api import collector_github_contents_api

with open(os.path.join(os.path.dirname(__file__), 'example_github_repo_contents_response.json')) as handle:
    RAW_CONTENTS = handle.read()
    JSON_CONTENTS = json.loads(RAW_CONTENTS)

EXAMPLE_CONTENT_JSON = [
    {
        "Description": "md5",
        "Identifier": "iubegr73b497fb398br9v3br98ufh3r"
    },
    {
        "Description": "",
        "Identifier": "iubegr73b497iubegr73b497fb398br9v3br98ufh3rfb398br9v3br98ufh3r"
    }
]
EXAMPLE_CONTENT_STR = str(EXAMPLE_CONTENT_JSON)

SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST = {
    'CONFIG': {
        'name': 'Github feed',
        'basic_auth_username': 'dummy_user',
        'basic_auth_password': 'dummy_password',
        'repository': 'author/repository',
        'extra_fields': 'size, sha',
        'regex': '.*.txt'
    },
    'EXPECTED_REPORTS': [
        {
            "__type": "Report",
            "feed.name": "Github feed",
            "feed.accuracy": 100.,
            "feed.url": JSON_CONTENTS[1]['download_url'],
            "raw": utils.base64_encode(EXAMPLE_CONTENT_STR),
            "extra.file_metadata": {
                "sha": JSON_CONTENTS[1]['sha'],
                "size": JSON_CONTENTS[1]['size']
            }
        }
    ]
}

SHOULD_FAIL_BECAUSE_REPOSITORY_IS_NOT_VALID_CONFIG = {
    'CONFIG': {
        'name': 'Github feed',
        'basic_auth_username': 'dummy_user',
        'basic_auth_password': 'dummy_password',
        'repository': 'author/',
        'extra_fields': 'size',
        'regex': '.*.txt'
    }
}

SHOULD_FAIL_WITH_BAD_CREDENTIALS = {
    'CONFIG': {
        'name': 'Github feed',
        'basic_auth_username': 'dummy_user',
        'basic_auth_password': 'bad_dummy_password',
        'repository': 'author/repo',
        'regex': '.*.txt'
    }
}


@requests_mock.Mocker()
class TestGithubContentsAPICollectorBot(test.BotTestCase, TestCase):
    """
    A TestCase for GithubContentsAPICollectorBot.
    """

    @classmethod
    def set_bot(cls):
        cls.bot_reference = collector_github_contents_api.GithubContentsAPICollectorBot

    def test_message_queue_should_contain_the_right_fields(self, mocker):
        mocker.get("https://api.github.com/repos/{0}/contents".format(SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG']['repository']), status_code=200, json=JSON_CONTENTS)
        mocker.get("https://a_download.url/contents.txt", status_code=200, text=EXAMPLE_CONTENT_STR)

        self.run_bot(parameters=SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG'], prepare=True)

        self.assertOutputQueueLen(len(SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['EXPECTED_REPORTS']))
        for i in range(len(self.get_output_queue())):
            self.assertMessageEqual(i, SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['EXPECTED_REPORTS'][i])

    def test_collector_should_fail_with_bad_repository_error(self, mocker):
        mocker.get("https://api.github.com/repos/{0}/contents".format(SHOULD_FAIL_BECAUSE_REPOSITORY_IS_NOT_VALID_CONFIG['CONFIG']['repository']))

        self.allowed_error_count = 1  # allow only single and final Error to be raised
        self.run_bot(parameters=SHOULD_FAIL_BECAUSE_REPOSITORY_IS_NOT_VALID_CONFIG['CONFIG'], prepare=True)
        self.assertRegexpMatchesLog(pattern=".*Unknown repository.*")  # assert the expected ValueError msg

    def test_collector_should_fail_with_bad_credentials(self, mocker):
        mocker.get("https://api.github.com/repos/{0}/contents".format(SHOULD_FAIL_WITH_BAD_CREDENTIALS['CONFIG']['repository']), status_code=401, json={'message': 'Bad Credentials'})

        self.allowed_error_count = 1
        self.run_bot(parameters=SHOULD_FAIL_WITH_BAD_CREDENTIALS['CONFIG'], prepare=True)
        self.assertRegexpMatchesLog(pattern=".*Bad Credentials.*")

    def test_adding_extra_fields_should_warn(self, mocker):
        mocker.get("https://api.github.com/repos/{0}/contents".format(SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG']['repository']), status_code=200, json=JSON_CONTENTS)
        mocker.get("https://a_download.url/contents.txt", status_code=200, text=EXAMPLE_CONTENT_STR)

        custom_config = SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG'].copy()
        custom_config['extra_fields'] = 'aaa,bbb'

        self.allowed_warning_count = 2
        self.run_bot(parameters=custom_config, prepare=True)

        self.assertRegexpMatchesLog(pattern=".*Field 'aaa' does not exist in the Github file data.*")
        self.assertRegexpMatchesLog(pattern=".*Field 'bbb' does not exist in the Github file data.*")
        self.assertMessageEqual(0, {
            "__type": "Report",
            "feed.name": "Github feed",
            "feed.accuracy": 100.,
            "feed.url": JSON_CONTENTS[1]['download_url'],
            "raw": utils.base64_encode(EXAMPLE_CONTENT_STR)
        })

    def test_collector_init_should_fail_with_invalid_argument(self, mocker):
        mocker.get("https://api.github.com/repos/{0}/contents".format(SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG']['repository']))

        custom_config = SHOULD_PASS_WITH_TXT_FILES_AND_EXTRA_FIELD_SIZE_TEST['CONFIG'].copy()

        config_with_wrong_regex = custom_config.copy()
        with self.assertRaises(exceptions.InvalidArgument):
            config_with_wrong_regex['regex'] = '*.txt'
            self.run_bot(parameters=config_with_wrong_regex, prepare=True)

        config_with_missing_regex = custom_config.copy()
        with self.assertRaises(exceptions.InvalidArgument):
            del config_with_missing_regex['regex']
            self.run_bot(parameters=config_with_missing_regex, prepare=True)

        config_with_missing_repository = custom_config.copy()
        with self.assertRaises(exceptions.InvalidArgument):
            del config_with_missing_repository['repository']
            self.run_bot(parameters=config_with_missing_repository, prepare=True)


if __name__ == '__main__':  # pragma: no cover
    unittest_main()

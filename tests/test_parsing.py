import sys
import os
import json
import pytest

# import pytest
file_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(1, f'{file_dir}/../orchestration/dag')
from parse_ada_data import check_int, parse_conversation_variables, check_order_num, deidentify, parse_list_selection_data, parse_surfaceable_list_selection_data, parse_presence_data, parse_quick_replies_data, parse_api_data


# This class is used to mock the output of the DlpServiceClient.deidentify_content in the test
# `test_parse_api_data_conversations`.
class Object():
    pass


def get_input_output_vars(file_name):
    with open(f'{file_dir}/inputs/{file_name}') as f1:
        input_data = json.load(f1) 
    with open(f'{file_dir}/outputs/{file_name}') as f2:
        output_data = json.load(f2)
    return (input_data, output_data)


# tests for check_int() function
def test_object_is_int():
    """Valid int should return the valid int"""
    assert check_int(1) == 1
    assert check_int("2") == 2


def test_object_is_not_int():
    """Invalid int should return the valid int"""
    assert check_int(1.5) == -1
    assert check_int("2.9") == -1
    assert check_int("Not an number") == -1
    assert check_int(None) == -1


def test_parse_conversation_variables():
    """Parse conversation vars into dictionary"""
    input_data, output_data = get_input_output_vars("parse_conversation_variables.json")
    assert parse_conversation_variables(input_data) == output_data


def test_check_order_num():
    """Test the order number checking function"""
    assert check_order_num("Not a number") == -1
    assert check_order_num("10.1") == -1
    assert check_order_num("531002571707350") == 531002571707350
    assert check_order_num('Ordered Online | Order# 531002607202011') == 531002607202011
    assert check_order_num(1983) == -1


def test_deidentify(mocker):
    obj = Object()
    obj.item = Object()
    obj.item.value = "example_text"
    mocker.patch("google.cloud.dlp_v2.services.dlp_service.client.DlpServiceClient.deidentify_content", return_value=obj)

    assert deidentify("conversations", "placeholder_project_name") == "example_text"
    assert deidentify(None, "placeholder_project_name") is None


def test_parse_list_selection_data():
    """Parse list_selection data into dictionary"""
    input_data, output_data = get_input_output_vars("parse_list_selection_data.json")
    assert parse_list_selection_data(input_data) == output_data
    assert parse_list_selection_data({}) is None


def test_parse_surfaceable_list_selection_data():
    """Parse surfaceable_list_selection data into dictionary"""
    input_data, output_data = get_input_output_vars("parse_surfaceable_list_selection_data.json")
    assert parse_surfaceable_list_selection_data(input_data) == output_data
    assert parse_surfaceable_list_selection_data({}) is None


def test_parse_presence_data():
    """Parse presence data into dictionary"""
    input_data, output_data = get_input_output_vars("parse_presence_data.json")
    assert parse_presence_data(input_data) == output_data
    assert parse_presence_data({}) is None


def test_quick_replies_data():
    """Parse quick_replies data into dictionary"""
    input_data, output_data = get_input_output_vars("parse_quick_replies_data.json")
    assert parse_quick_replies_data(input_data) == output_data
    assert parse_quick_replies_data({}) is None


def test_quick_replies_data():
    """Parse quick_replies data into dictionary"""
    input_data, output_data = get_input_output_vars("parse_quick_replies_data.json")
    assert parse_quick_replies_data(input_data) == output_data
    assert parse_quick_replies_data({}) is None

def test_parse_api_data_messages():
    """Parse a full response from the messages API"""
    input_data, output_data = get_input_output_vars("response_messages.json")
    assert parse_api_data(input_data, "messages", "placeholder_project_name") == output_data


def test_parse_api_data_conversations(mocker):
    """Parse a full response from the conversations API"""
    obj = Object()
    obj.item = Object()
    obj.item.value = "example_text"
    mocker.patch("google.cloud.dlp_v2.services.dlp_service.client.DlpServiceClient.deidentify_content", return_value=obj)

    input_data, output_data = get_input_output_vars("response_conversations.json")
    assert parse_api_data(input_data, "conversations", "placeholder_project_name") == output_data


def test_exception_thrown():
    with pytest.raises(Exception) as e_info:
        parse_api_data([], "Incorrect API type input", "placeholder_project_name")

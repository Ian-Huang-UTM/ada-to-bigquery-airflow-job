import logging as log
import re

from google.cloud import dlp_v2


#########################################
#                                       #
#               PARSING                 #
#                                       #
#########################################
def parse_api_data(valid_response_data, data_type, project):
    log.info("Begin parsing %s data.", data_type)
    if data_type == "conversations":
        parsed_data = parse_conversation_list(valid_response_data, project)
    elif data_type == "messages":
        parsed_data = parse_message_list(valid_response_data, project)
    else:
        raise Exception(f"Error in parsing: '{data_type}' is not a recognized data type.")
    log.info("Done parsing %s.", data_type)
    return parsed_data


def check_int(val):
    if str(val).isdigit():
        return int(val)
    return -1


#########################################
#                                       #
#            CONVERSATIONS              #
#                                       #
#########################################
def parse_conversation_list(valid_response_data, project):
    return [parse_conversation(conversation_data, project)
            for conversation_data
            in valid_response_data]


def parse_conversation(conversation_response, project):
    """Parse a single instance of conversation data into a BigQuery readable dict."""
    return {"conversation_id": conversation_response["_id"],
            "date_updated": conversation_response["date_updated"].split("+")[0],
            "date_created": conversation_response["date_created"].split("+")[0],
            "chatter_id": conversation_response["chatter_id"],
            "platform": conversation_response["platform"],
            "is_engaged": conversation_response["is_engaged"],
            "is_escalated": conversation_response["is_escalated"],
            "csat": str(conversation_response["csat"]),
            "variables": parse_conversation_variables(
                conversation_response["variables"]),
            "metavariables": parse_conversation_metavars(
                conversation_response["metavariables"], project),
            "conversation_obj": str(conversation_response),
            }


def parse_conversation_metavars(conv_metavariables, project):
    return {
        "browser": conv_metavariables.get("browser"),
        "browser_version": conv_metavariables.get("browser_version"),
        "chattertoken": conv_metavariables.get("chattertoken"),
        "created": check_int(conv_metavariables.get("created")),
        "device": conv_metavariables.get("device"),
        "embed": check_int(conv_metavariables.get("embed")),
        "followupresponseid": conv_metavariables.get("followupresponseid"),
        "initialurl": conv_metavariables.get("initialurl"),
        "introshown": conv_metavariables.get("introshown"),
        "language": conv_metavariables.get("language"),
        "last_answer_id": conv_metavariables.get("last_answer_id"),
        "last_question_asked": deidentify(conv_metavariables.get("last_question_asked"), project),
        "user_agent": conv_metavariables.get("user_agent"),
    }


def check_order_num(order_num_string: str) -> int:
    if not isinstance(order_num_string, str):
        return -1
    regex_pattern = r"(?<!\d)\d{15}(?!\d)|$"
    regex_str_found = re.search(regex_pattern, order_num_string).group()
    if regex_str_found == '':
        return -1
    return int(regex_str_found)


def parse_conversation_variables(conv_variables):
    return {
        "domain_name": conv_variables.get("domain_name"),
        "lob": conv_variables.get("lob"),
        "order_number": check_order_num(conv_variables.get("order number")),
    }


#########################################
#                                       #
#              MESSAGES                 #
#                                       #
#########################################
def parse_message_list(valid_response_data, project):
    return [parse_message(message_data, project)
            for message_data
            in valid_response_data]


def parse_message(message_response, project):
    m_data = message_response["message_data"]
    sender = message_response["sender"]
    return {"message_id": message_response["_id"],
            "date_created": message_response["date_created"].split("+")[0],
            "conversation_id": message_response["conversation_id"],
            "message_type": message_response["message_data"].get("_type"),
            "text_data": parse_text_data(m_data, project, sender),
            "quick_replies_data": parse_quick_replies_data(m_data),
            "trigger_data": parse_trigger_data(m_data),
            "presence_data": parse_presence_data(m_data),
            "list_selection_data": parse_list_selection_data(m_data),
            "surfaceable_list_selection_data": parse_surfaceable_list_selection_data(m_data),
            "sender": sender,
            "recipient": message_response["recipient"],
            "review": message_response["review"],
            "answer_title": message_response["answer_title"],
            "message_obj": str(message_response),
            }


def parse_text_data(message_data, project, sender):
    '''Format here'''
    if message_data.get("_type") != "text":
        return None
    body = message_data.get("body").encode("ascii", "ignore").decode()
    deidentified_body = body if sender in ("bot", "ada") else deidentify(body, project)
    return {
        "body": deidentified_body,
        "has_variables": message_data.get("has_variables"),
        "reviewable_message": message_data.get("reviewable_message"),
        "has_forced_quick_replies": message_data.get("has_forced_quick_replies"),
    }


def parse_quick_replies_data(message_data):
    '''Format here'''
    if message_data.get("_type") != "quick_replies":
        return None
    reply_list = message_data.get("quick_replies")
    return {
        "is_forced": message_data.get("is_forced"),
        "has_variables": message_data.get("has_variables"),
        # TODO: Parse quick_replies into separate button records
        "quick_replies": str(reply_list),
        "reviewable_message": message_data.get("reviewable_message"),
    }


def parse_trigger_data(message_data):
    '''Format here'''
    if message_data.get("_type") != "trigger":
        return None
    return {
        "body": message_data.get("body"),
        "button_type": message_data.get("button_type"),
        "external_chat_id": message_data.get("external_chat_id"),
        "reviewable_message": message_data.get("reviewable_message"),
    }


def parse_presence_data(message_data):
    '''Format here'''
    if message_data.get("_type") != "presence":
        return None
    return {
        "body": message_data.get("body"),
        "event": message_data.get("event"),
        "has_variables": message_data.get("has_variables"),
        "reviewable_message": message_data.get("reviewable_message"),
    }


def parse_list_selection_data(message_data):
    '''Format here'''
    if message_data.get("_type") != "list_selection":
        return None
    return {
        "body": message_data.get("body"),
        "by": message_data.get("by"),
        "created": message_data.get("created"),
        "data": str(message_data.get("data")),  # TODO: parse subfields of JSON into record
        "external_chat_id": message_data.get("external_chat_id"),
        "platform": message_data.get("platform"),
        "reviewable_message": message_data.get("reviewable_message"),
        "temp_message_uuid": message_data.get("temp_message_uuid"),
        "to": message_data.get("to"),
    }


def parse_surfaceable_list_selection_data(message_data):
    '''Format here'''
    if message_data.get("_type") != "surfaceable_list_selection":
        return None
    return {
        "has_variables": message_data.get("has_variables"),
        "is_expired": message_data.get("is_expired"),
        "locked": message_data.get("locked"),
        "multiple": message_data.get("multiple"),
        "prompt": message_data.get("prompt"),
        "reviewable_message": message_data.get("reviewable_message"),
        "selectables": str(message_data.get("selectables")),
    }


#########################################
#                                       #
#          DATA LOSS PREVENTION         #
#                                       #
#########################################
def deidentify(input_str, project):
    """Uses the Data Loss Prevention API to deidentify sensitive data in a
    string by replacing matched input values with a value you specify.
    """

    if not input_str:
        return input_str

    info_types = [
        "CREDIT_CARD_NUMBER",
        "EMAIL_ADDRESS",
        "FIRST_NAME",
        "LAST_NAME",
        "PERSON_NAME",
        "PHONE_NUMBER",
        "STREET_ADDRESS",
    ]
    # Instantiate a client
    dlp = dlp_v2.DlpServiceClient()

    # Convert the project id into a full resource id.
    parent = f"projects/{project}"

    # Construct inspect configuration dictionary
    inspect_config = {
        "info_types": [{"name": info_type} for info_type in info_types],
        "min_likelihood": "UNLIKELY",
    }

    # Construct deidentify configuration dictionary
    deidentify_config = {
        "info_type_transformations": {
            "transformations": [
                {
                    "primitive_transformation": {
                        "replace_with_info_type_config": {},
                    },
                },
            ],
        },
    }

    # Construct item
    item = {"value": input_str}

    # Call the API
    response = dlp.deidentify_content(
        parent, deidentify_config=deidentify_config, item=item, inspect_config=inspect_config)

    # Return the results.
    return response.item.value

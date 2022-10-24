#!/usr/bin/python3


"""Telepathy cli interface:
    An OSINT toolkit for investigating Telegram chats.
"""

from tokenize import group
import pandas as pd
import datetime
import requests
import json
import random
import glob
import csv
import os
import getpass
import click
import re
import textwrap
import time
import pprint

from telepathy.utils import (
    print_banner,
    color_print_green,
    populate_user,
    process_message,
    process_description,
    parse_tg_date,
    parse_html_page,
    print_shell
)
import const as const

from colorama import Fore, Back, Style

from telethon.errors import SessionPasswordNeededError, ChannelPrivateError
from telethon.tl.types import (
    InputPeerEmpty,
    PeerUser,
    PeerChat,
    PeerChannel,
    PeerLocated,
    ChannelParticipantCreator,
    ChannelParticipantAdmin,
)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon import TelegramClient, functions, types, utils
from telethon.utils import get_display_name, get_message_id
from alive_progress import alive_bar
from bs4 import BeautifulSoup


@click.command()
@click.option(
    "--target",
    "-t",
    #default="",
    multiple=True,
    help="Specifies a chat to investigate.",
)
@click.option(
    "--comprehensive",
    "-c",
    is_flag=True,
    help="Comprehensive scan, includes archiving.",
)
@click.option(
    "--media", "-m", is_flag=True, help="Archives media in the specified chat."
)
@click.option("--forwards", "-f", is_flag=True, help="Scrapes forwarded messages.")
@click.option("--user", "-u", is_flag=True, help="Looks up a specified user ID.")
@click.option(
    "--location", "-l", is_flag=True, help="Finds users near to specified coordinates."
)
@click.option(
    "--alt", "-a", is_flag=True, default=False, help="Uses an alternative login."
)
@click.option("--json", "-j", is_flag=True, default=False, help="Export to JSON.")
@click.option(
    "--export",
    "-e",
    is_flag=True,
    default=False,
    help="Export a list of chats your account is part of.",
)
@click.option(
    "--replies",
    "-r",
    is_flag=True,
    default=False,
    help="Enable replies analysis in channels.",
)
def cli(
    target, comprehensive, media, forwards, user, location, alt, json, export, replies
):
    print_banner()
    telepathy_file = "./telepathy_files/"
    try:
        os.makedirs(telepathy_file)
    except FileExistsError:
        pass

    # Defining default values
    basic = False
    comp_check = False
    media_archive = False
    forwards_check = False
    forward_verify = False
    reply_analysis = False
    user_check = False
    location_check = False
    last_date = None
    chunk_size = 1000
    filetime = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M")
    filetime_clean = str(filetime)

    # Will add more languages later
    user_language = "en"

    if target:
        basic = True
    if replies:
        reply_analysis = True
    if forwards:
        forwards_check = True
    if user:
        user_check = True
        basic = False
    if location:
        location_check = True
        basic = False
    if comprehensive:
        comp_check = True
    if media:
        media_archive = True
    if export:
        t = " "
    if alt:
        alt_check = True
    else:
        alt_check = False

    if json:
        json_check = True
        json_file = telepathy_file + "json_files/"
        try:
            os.makedirs(json_file)
        except FileExistsError:
            pass
    else:
        json_check = False

    if alt_check == True:
        login = telepathy_file + "login_alt.txt"

        if os.path.isfile(login) == False:
            api_id = input(" Please enter your API ID:\n")
            api_hash = input(" Please enter your API Hash:\n")
            phone_number = input(" Please enter your phone number:\n")
            with open(login, "w+", encoding="utf-8") as f:
                f.write(api_id + "," + api_hash + "," + phone_number)
        else:
            with open(login, encoding="utf-8") as f:
                details = f.read()
                api_id, api_hash, phone_number = details.split(sep=",")
    else:
        login = telepathy_file + "login.txt"

        if os.path.isfile(login) == False:
            api_id = input(" Please enter your API ID:\n")
            api_hash = input(" Please enter your API Hash:\n")
            phone_number = input(" Please enter your phone number:\n")
            with open(login, "w+", encoding="utf-8") as f:
                f.write(api_id + "," + api_hash + "," + phone_number)
        else:
            with open(login, encoding="utf-8") as f:
                details = f.read()
                api_id, api_hash, phone_number = details.split(sep=",")

    client = TelegramClient(phone_number, api_id, api_hash)

    async def main():

        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
            await client.sign_in(phone_number)
            try:
                await client.sign_in(code=input(" Enter code: "))
            except SessionPasswordNeededError:
                await client.sign_in(
                    password=getpass.getpass(prompt="Password: ", stream=None)
                )
            result = client(
                GetDialogsRequest(
                    offset_date=last_date,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=chunk_size,
                    hash=0,
                )
            )
        else:

            if export == True:
                export_file = telepathy_file + "export.csv"
                exports = []

                print("Exporting...")

                # progress bar

                for Dialog in await client.get_dialogs():
                    try:
                        if Dialog.entity.username:
                            group_url = "http://t.me/" + Dialog.entity.username
                            group_username = Dialog.entity.username

                            web_req = parse_html_page(group_url)
                            group_description = web_req["group_description"]
                            total_participants = web_req["total_participants"]

                            _desc = process_description(
                                group_description, user_language
                                )
                            translated_description = _desc["translated_text"]

                            if Dialog.entity.broadcast is True:
                                chat_type = "Channel"
                            elif Dialog.entity.megagroup is True:
                                chat_type = "Megagroup"
                            elif Dialog.entity.gigagroup is True:
                                chat_type = "Gigagroup"
                            else:
                                chat_type = "Chat"

                            if Dialog.entity.restriction_reason is not None:
                                ios_restriction = Dialog.entity.restriction_reason[
                                    0
                                ]
                                if 1 in Dialog.entity.restriction_reason:
                                    android_restriction = (
                                        Dialog.entity.restriction_reason[1]
                                    )
                                    group_status = (
                                        str(ios_restriction)
                                        + ", "
                                        + str(android_restriction)
                                    )
                                else:
                                    group_status = str(ios_restriction)
                            else:
                                group_status = "None"

                            exports.append(
                                [
                                    filetime,
                                    Dialog.entity.title,
                                    group_description,
                                    translated_description,
                                    total_participants,
                                    group_username,
                                    group_url,
                                    chat_type,
                                    Dialog.entity.id,
                                    Dialog.entity.access_hash,
                                    group_status,
                                ]
                            )

                            export_df = pd.DataFrame(
                                exports,
                                columns=[
                                    "Access Date",
                                    "Title",
                                    "Description",
                                    "Translated description",
                                    "Total participants",
                                    "Username",
                                    "URL",
                                    "Chat type",
                                    "Chat ID",
                                    "Access hash",
                                    "Restrictions",
                                ],
                            )

                            if not os.path.isfile(export_file):
                                export_df.to_csv(export_file, sep=";", index=False)
                            else:
                                export_df.to_csv(
                                    export_file, sep=";", mode="w", index=False
                                )

                    except AttributeError:
                        pass

            else:

                for t in target:
                    target_clean = t
                    alphanumeric = ""
                    

                    for character in target_clean:
                        if character.isalnum():
                            alphanumeric += character

                    if "https://t.me/+" in t:
                        t = t.replace('https://t.me/+', 'https://t.me/joinchat/')

                    if basic is True or comp_check is True:
                        save_directory = telepathy_file + alphanumeric
                        try:
                            os.makedirs(save_directory)
                        except FileExistsError:
                            pass

                    # Creating logfile
                    log_file = telepathy_file + "log.csv"

                    if media_archive:
                        media_directory = save_directory + "/media"
                        try:
                            os.makedirs(media_directory)
                        except FileExistsError:
                            pass

                    if basic == True and comp_check == False:
                        color_print_green(" [!] ", "Performing basic scan")
                    elif comp_check == True:
                        color_print_green(" [!] ", "Performing comprehensive scan")
                        file_archive = (
                            save_directory
                            + "/"
                            + alphanumeric
                            + "_"
                            + filetime_clean
                            + "_archive.csv"
                        )
                        reply_file_archive = (
                            save_directory
                            + "/"
                            + alphanumeric
                            + "_"
                            + filetime_clean
                            + "_reply_archive.csv"
                        )

                    if forwards_check == True:
                        color_print_green(" [!] ", "Forwards will be fetched")
                        file_forwards = (
                            save_directory
                            + "/edgelists/"
                            + alphanumeric
                            + "_"
                            + filetime_clean
                            + "_edgelist.csv"
                        )
                        forward_directory = save_directory + "/edgelists/"

                        try:
                            os.makedirs(forward_directory)
                        except FileExistsError:
                            pass

                        edgelist_file = (
                            forward_directory + "/" + alphanumeric + "_edgelist.csv"
                        )

                    if basic is True or comp_check is True:

                        color_print_green(" [-] ", "Fetching details for " + t + "...")
                        memberlist_directory = save_directory + "/memberlists"

                        try:
                            os.makedirs(memberlist_directory)
                        except FileExistsError:
                            pass

                        memberlist_filename = (
                            memberlist_directory + "/" + alphanumeric + "_members.csv"
                        )
                        reply_memberlist_filename = (
                            memberlist_directory
                            + "/"
                            + alphanumeric
                            + "_active_members.csv"
                        )

                        entity = await client.get_entity(t)
                        first_post = "Not found"

                        async for message in client.iter_messages(t, reverse=True):
                            datepost = parse_tg_date(message.date)
                            date = datepost["date"]
                            mtime = datepost["mtime"]
                            first_post = datepost["timestamp"]
                            break

                        if entity.username:
                            name = entity.title
                            group_url = "http://t.me/" + entity.username
                            group_username = entity.username
                            web_req = parse_html_page(group_url)
                        elif "https://t.me/" in t:
                            group_url = t
                            web_req = parse_html_page(group_url)
                            group_username = "Private group"
                        else:
                            group_url = "Private group"
                            group_username = "Private group"


                        group_description = web_req["group_description"]
                        total_participants = web_req["total_participants"]

                        _desc = process_description(
                            group_description, user_language
                            )

                        original_language = _desc[
                            "original_language"
                        ]

                        translated_description = _desc["translated_text"]

                        preferredWidth = 70
                        descript = Fore.GREEN + "Description: " + Style.RESET_ALL
                        prefix = descript 
                        wrapper_d = textwrap.TextWrapper(
                            initial_indent=prefix,
                            width=preferredWidth,
                            subsequent_indent="                  ",
                        )

                        trans_descript = Fore.GREEN + "Translated: " + Style.RESET_ALL
                        prefix = trans_descript
                        wrapper_td = textwrap.TextWrapper(
                            initial_indent=prefix,
                            width=preferredWidth,
                            subsequent_indent="                  ",
                        )

                        group_description = ('"' + group_description + '"')

                        if entity.broadcast is True:
                            chat_type = "Channel"
                        elif entity.megagroup is True:
                            chat_type = "Megagroup"
                        elif entity.gigagroup is True:
                            chat_type = "Gigagroup"
                        else:
                            chat_type = "Chat"

                        if entity.restriction_reason is not None:
                            ios_restriction = entity.restriction_reason[0]
                            if 1 in entity.restriction_reason:
                                android_restriction = entity.restriction_reason[1]
                                group_status = (
                                    str(ios_restriction) + ", " + str(android_restriction)
                                )
                            else:
                                group_status = str(ios_restriction)
                        else:
                            group_status = "None"

                        restrict = Fore.GREEN + "Restrictions:" + Style.RESET_ALL
                        prefix = restrict + " "
                        preferredWidth = 70
                        wrapper_r = textwrap.TextWrapper(
                            initial_indent=prefix,
                            width=preferredWidth,
                            subsequent_indent="                   ",
                        )
                        found_participants = 0
                        found_participants = 0

                        if chat_type != "Channel":
                            members = []
                            all_participants = []
                            all_participants = await client.get_participants(t, limit=5000)

                            members_df = None
                            for user in all_participants:
                                members_df = pd.DataFrame(
                                    members,
                                    columns=[
                                        "Username",
                                        "Full name",
                                        "User ID",
                                        "Phone number",
                                        "Group name",
                                    ],
                                )
                                members.append(populate_user(user, t))

                            if members_df is not None:
                                with open(
                                    memberlist_filename, "w+", encoding="utf-8"
                                ) as save_members:
                                    members_df.to_csv(save_members, sep=";")

                                if json_check == True:
                                    members_df.to_json(
                                        json_file + alphanumeric + "_memberlist.json",
                                        orient="records",
                                        compression="infer",
                                        lines=True,
                                        index=True,
                                    )
                                else:
                                    pass

                            found_participants = len(all_participants)
                            found_participants = int(found_participants)
                            found_percentage = (
                                int(found_participants) / int(total_participants) * 100
                            )

                        log = []

                        if chat_type != "Channel":
                            print("\n")
                            color_print_green(" [+] Memberlist fetched", "")
                        else:
                            pass

                        setattr(entity, "group_description", group_description)
                        setattr(entity, "group_status", group_status)
                        setattr(entity, "group_username", group_username)
                        setattr(entity, "first_post", first_post)
                        setattr(entity, "group_url", group_url)
                        setattr(entity, "chat_type", chat_type)
                        setattr(entity, "translated_description", translated_description)
                        setattr(entity, "total_participants", total_participants)
                        if chat_type != "Channel":
                            setattr(entity, "found_participants", found_participants)
                            setattr(entity, "found_percentage", found_percentage)
                            setattr(entity, "memberlist_filename", memberlist_filename)
                        else:
                            setattr(entity, "found_participants", found_participants)
                        print_flag = "group_recap"
                        if chat_type == "Channel":
                            print_flag = "channel_recap"

                        print_shell(print_flag, entity)

                        log.append(
                            [
                                filetime,
                                entity.title,
                                group_description,
                                translated_description,
                                total_participants,
                                found_participants,
                                group_username,
                                group_url,
                                chat_type,
                                entity.id,
                                entity.access_hash,
                                str(entity.scam),
                                date,
                                mtime,
                                group_status,
                            ]
                        )

                        log_df = pd.DataFrame(
                            log,
                            columns=[
                                "Access Date",
                                "Title",
                                "Description",
                                "Translated description",
                                "Total participants",
                                "Participants found",
                                "Username",
                                "URL",
                                "Chat type",
                                "Chat ID",
                                "Access hash",
                                "Scam",
                                "First post date",
                                "First post time (UTC)",
                                "Restrictions",
                            ],
                        )

                        if not os.path.isfile(log_file):
                            log_df.to_csv(log_file, sep=";", index=False)
                        else:
                            log_df.to_csv(
                                log_file, sep=";", mode="a", index=False, header=False
                            )

                        if forwards_check is True and comp_check is False:
                            color_print_green(
                                " [-] ", "Calculating number of forwarded messages..."
                            )
                            forwards_list = []
                            forward_count = 0
                            private_count = 0
                            to_ent = await client.get_entity(t)
                            to_title = to_ent.title

                            forwards_df = pd.DataFrame(
                                forwards_list,
                                columns=[
                                    "Source",
                                    "Target",
                                    "Label",
                                    "Source_ID",
                                    "Username",
                                    "Timestamp",
                                ],
                            )

                            async for message in client.iter_messages(t):
                                if message.forward is not None:
                                    forward_count += 1

                            #print("\n")
                            color_print_green(" [-] ", "Fetching forwarded messages...")

                            progress_bar = (
                                Fore.GREEN + " [-] " + Style.RESET_ALL + "Progress: "
                            )

                            with alive_bar(
                                forward_count, dual_line=True, title=progress_bar, length=20
                            ) as bar:

                                async for message in client.iter_messages(t):
                                    if message.forward is not None:
                                        try:
                                            f_from_id = message.forward.original_fwd.from_id
                                            if f_from_id is not None:
                                                ent = await client.get_entity(f_from_id)
                                                username = ent.username
                                                timestamp = parse_tg_date(message.date)[
                                                    "timestamp"
                                                ]

                                                substring = "PeerUser"
                                                string = str(f_from_id)
                                                if substring in string:
                                                    user_id = re.sub("[^0-9]", "", string)
                                                    user_id = await client.get_entity(
                                                        PeerUser(int(user_id))
                                                    )
                                                    user_id = str(user_id)
                                                    result = (
                                                        "User: "
                                                        + str(ent.first_name)
                                                        + " / ID: "
                                                        + str(user_id.id)
                                                    )
                                                else:
                                                    result = str(ent.title)

                                                forwards_df = pd.DataFrame(
                                                    forwards_list,
                                                    columns=[
                                                        "Source",
                                                        "Target",
                                                        "Label",
                                                        "Source_ID",
                                                        "Username",
                                                        "Timestamp",
                                                    ],
                                                )

                                                forwards_list.append(
                                                    [
                                                        result,
                                                        t,
                                                        to_title,
                                                        f_from_id,
                                                        username,
                                                        timestamp,
                                                    ]
                                                )

                                        except Exception as e:
                                            if e is ChannelPrivateError:
                                                print("Private channel")
                                            continue

                                        time.sleep(0.5)
                                        bar()

                                        with open(
                                            edgelist_file, "w+", encoding="utf-8"
                                        ) as save_forwards:
                                            forwards_df.to_csv(save_forwards, sep=";")

                                        if json_check == True:
                                            forwards_df.to_json(
                                                json_file + alphanumeric + "_edgelist.json",
                                                orient="records",
                                                compression="infer",
                                                lines=True,
                                                index=True,
                                            )
                                        else:
                                            pass

                            if forward_count >= 15:
                                forwards_found = forwards_df.Source.count()
                                value_count = forwards_df["Source"].value_counts()
                                df01 = value_count.rename_axis("unique_values").reset_index(
                                    name="counts"
                                )

                                report_forward = object()
                                setattr(report_forward, "forward_one", (
                                    str(df01.iloc[0]["unique_values"])
                                    + ", "
                                    + str(df01.iloc[0]["counts"])
                                    + " forwarded messages"
                                ))
                                setattr(report_forward, "forward_two", (
                                    str(df01.iloc[1]["unique_values"])
                                    + ", "
                                    + str(df01.iloc[1]["counts"])
                                    + " forwarded messages"
                                ))
                                setattr(report_forward, "forward_three", (
                                    str(df01.iloc[2]["unique_values"])
                                    + ", "
                                    + str(df01.iloc[2]["counts"])
                                    + " forwarded messages"
                                ))
                                setattr(report_forward, "forward_four", (
                                    str(df01.iloc[3]["unique_values"])
                                    + ", "
                                    + str(df01.iloc[3]["counts"])
                                    + " forwarded messages"
                                ))
                                setattr(report_forward, "forward_five", (
                                    str(df01.iloc[4]["unique_values"])
                                    + ", "
                                    + str(df01.iloc[4]["counts"])
                                    + " forwarded messages"
                                ))

                                df02 = forwards_df.Source.unique()
                                setattr(report_forward, "unique_forwards", len(df02))
                                setattr(report_forward, "edgelist_file", len(df02))
                                print_shell("forwarder_stat",report_forward)

                            else:
                                print(
                                    "\n"
                                    + Fore.GREEN
                                    + " [!] Insufficient forwarded messages found"
                                    + Style.RESET_ALL
                                )

                        else:

                            if comp_check is True:

                                messages = client.iter_messages(t)
                                message_list = []
                                forwards_list = []
                                user_reaction_list = []
                                replies_list = []
                                user_replier_list = []
                                timecount = []
                                forward_count = 0
                                private_count = 0

                                if media_archive is True:
                                    files = []
                                    print("\n")
                                    color_print_green(
                                        " [!] ", "Media content will be archived"
                                    )

                                color_print_green(
                                    " [!] ", "Calculating number of messages..."
                                )

                                message_count = 0

                                async for message in messages:
                                    if message is not None:
                                        message_count += 1

                                print("\n")
                                color_print_green(" [-] ", "Fetching message archive...")
                                progress_bar = (
                                    Fore.GREEN + " [-] " + Style.RESET_ALL + "Progress: "
                                )

                                with alive_bar(
                                    message_count,
                                    dual_line=True,
                                    title=progress_bar,
                                    length=20,
                                ) as bar:

                                    to_ent = await client.get_entity(t)

                                    async for message in client.iter_messages(
                                        t, limit=None
                                    ):
                                        if message is not None:

                                            try:

                                                c_archive = pd.DataFrame(
                                                    message_list,
                                                    columns=[
                                                        "To",
                                                        "Message ID",
                                                        "Display_name",
                                                        "ID",
                                                        "Message_text",
                                                        "Original_language",
                                                        "Translated_text",
                                                        "Translation_confidence",
                                                        "Timestamp",
                                                        "Has_media",
                                                        "Reply",
                                                        "Views",
                                                        "URL",
                                                    ],
                                                )

                                                c_forwards = pd.DataFrame(
                                                    forwards_list,
                                                    columns=[
                                                        "Source",
                                                        "Target",
                                                        "Label",
                                                        "Source_ID",
                                                        "Username",
                                                        "Timestamp",
                                                    ],
                                                )

                                                #if message.reactions:
                                                #    if message.reactions.can_see_list:
                                                #        c_reactioneer = pd.DataFrame(
                                                #            user_reaction_list,
                                                #            columns=[
                                                #                "Username",
                                                #                "Full name",
                                                #                "User ID",
                                                #                "Phone number",
                                                #                "Group name",
                                                #            ],
                                                #        )

                                                if (
                                                    message.replies
                                                    and reply_analysis
                                                    and chat_type == "Channel"
                                                ):
                                                    if message.replies.replies > 0:
                                                        c_repliers = pd.DataFrame(
                                                            user_replier_list,
                                                            columns=[
                                                                "Username",
                                                                "Full name",
                                                                "User ID",
                                                                "Phone number",
                                                                "Group name",
                                                            ],
                                                        )
                                                        
                                                        c_replies = pd.DataFrame(
                                                            replies_list,
                                                            columns=[
                                                                "To",
                                                                "Message ID",
                                                                "Reply ID",
                                                                "Display_name",
                                                                "User ID",
                                                                "Message_text",
                                                                "Original_language",
                                                                "Translated_text",
                                                                "Translation_confidence",
                                                                "Timestamp",
                                                            ],
                                                        )

                                                if message.replies:
                                                    if message.replies.replies > 0:
                                                        async for repl in client.iter_messages(
                                                            message.chat_id,
                                                            reply_to=message.id,
                                                        ):
                                                            user = await client.get_entity(
                                                                repl.from_id.user_id
                                                            )
                                                            userdet = populate_user(user, t)
                                                            user_replier_list.append(
                                                                userdet
                                                            )
                                                            mss_txt = process_message(
                                                                repl.text, user_language
                                                            )
                                                            replies_list.append(
                                                                [
                                                                    t,
                                                                    message.id,
                                                                    repl.id,
                                                                    userdet[1],
                                                                    userdet[2],
                                                                    mss_txt["message_text"],
                                                                    mss_txt[
                                                                        "original_language"
                                                                    ],
                                                                    mss_txt[
                                                                        "translated_text"
                                                                    ],
                                                                    mss_txt[
                                                                        "translation_confidence"
                                                                    ],
                                                                    parse_tg_date(
                                                                        repl.date
                                                                    )["timestamp"],
                                                                ]
                                                            )

                                                display_name = get_display_name(
                                                    message.sender
                                                )
                                                if chat_type != "Channel":
                                                    substring = "PeerUser"
                                                    string = str(message.from_id)
                                                    if substring in string:
                                                        user_id = re.sub(
                                                            "[^0-9]", "", string
                                                        )
                                                        nameID = str(user_id)
                                                    else:
                                                        nameID = str(message.from_id)
                                                else:
                                                    nameID = to_ent.id

                                                timestamp = parse_tg_date(message.date)[
                                                    "timestamp"
                                                ]
                                                reply = message.reply_to_msg_id

                                                _mess = process_message(
                                                    message.text, user_language
                                                )
                                                message_text = _mess["message_text"]
                                                original_language = _mess[
                                                    "original_language"
                                                ]
                                                translated_text = _mess["translated_text"]
                                                translation_confidence = _mess[
                                                    "translation_confidence"
                                                ]

                                                if message.forwards is not None:
                                                    forwards = int(message.forwards)
                                                else:
                                                    forwards = "None"

                                                if message.views is not None:
                                                    views = int(message.views)
                                                else:
                                                    views = "Not found"

                                                #if message.reactions:
                                                    #if message.reactions.can_see_list:
                                                        #print(dir(message.reactions.results))
                                                        #print("#### TODO: REACTIONS")

                                                if media_archive == True:
                                                    if message.media:
                                                        path = await message.download_media(
                                                            file=media_directory
                                                        )
                                                        files.append(path)
                                                    else:
                                                        pass
                                                
                                                if message.media is not None:
                                                    has_media = "TRUE"
                                                else:
                                                    has_media = 'FALSE'

                                                post_url = "https://t.me/s/" + t + "/" + message.id

                                                message_list.append(
                                                    [
                                                        t,
                                                        message.id,
                                                        display_name,
                                                        nameID,
                                                        message_text,
                                                        original_language,
                                                        translated_text,
                                                        translation_confidence,
                                                        timestamp,
                                                        has_media,
                                                        reply,
                                                        views,
                                                        post_url,
                                                    ]
                                                )

                                                if message.forward is not None:
                                                    forward_verify = True
                                                    try:
                                                        forward_count += 1
                                                        to_title = to_ent.title
                                                        f_from_id = (
                                                            message.forward.original_fwd.from_id
                                                        )

                                                        if f_from_id is not None:
                                                            ent = await client.get_entity(
                                                                f_from_id
                                                            )
                                                            user_string = "user_id"
                                                            channel_string = "broadcast"

                                                            if user_string in str(ent):
                                                                ent_type = "User"
                                                            else:
                                                                if channel_string in str(
                                                                    ent
                                                                ):
                                                                    if (
                                                                        ent.broadcast
                                                                        is True
                                                                    ):
                                                                        ent_type = "Channel"
                                                                    elif (
                                                                        ent.megagroup
                                                                        is True
                                                                    ):
                                                                        ent_type = (
                                                                            "Megagroup"
                                                                        )
                                                                    elif (
                                                                        ent.gigagroup
                                                                        is True
                                                                    ):
                                                                        ent_type = (
                                                                            "Gigagroup"
                                                                        )
                                                                    else:
                                                                        ent_type = "Chat"
                                                                else:
                                                                    continue

                                                            if ent.username is not None:
                                                                username = ent.username
                                                            else:
                                                                username = "none"

                                                            if ent_type != "Chat":
                                                                result = str(ent.title)
                                                            else:
                                                                result = "none"

                                                            if ent_type == "User":
                                                                substring_1 = "PeerUser"
                                                                string_1 = str(ent.user_id)
                                                                if substring_1 in string_1:
                                                                    user_id = re.sub(
                                                                        "[^0-9]",
                                                                        "",
                                                                        string_1,
                                                                    )
                                                                    user_id = await client.get_entity(
                                                                        PeerUser(
                                                                            int(user_id)
                                                                        )
                                                                    )
                                                                    user_id = str(user_id)
                                                                    result = (
                                                                        "User: "
                                                                        + str(
                                                                            ent.first_name
                                                                        )
                                                                        + " / ID: "
                                                                        + str(user_id)
                                                                    )
                                                                else:
                                                                    result = str(ent.title)
                                                            else:
                                                                result = str(ent.title)

                                                            forwards_list.append(
                                                                [
                                                                    result,
                                                                    t,
                                                                    to_title,
                                                                    f_from_id,
                                                                    username,
                                                                    timestamp,
                                                                ]
                                                            )

                                                    except ChannelPrivateError:
                                                        private_count += 1
                                                        continue

                                                    except Exception as e:
                                                        print("An exception occurred.", e)
                                                        continue

                                            except Exception as e:
                                                print("An exception occurred.", e)

                                        else:
                                            message_list.append(
                                                [
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                    "None",
                                                ]
                                            )
                                            pass

                                        time.sleep(0.5)
                                        bar()

                                if reply_analysis is True:
                                    if len(replies_list) > 0:
                                        with open(
                                            reply_file_archive, "w+", encoding="utf-8"
                                        ) as rep_file:
                                            c_replies.to_csv(rep_file, sep=";")

                                    if len(user_replier_list) > 0:
                                        with open(
                                            reply_memberlist_filename, "w+", encoding="utf-8"
                                        ) as repliers_file:
                                            c_repliers.to_csv(repliers_file, sep=";")

                                with open(
                                    file_archive, "w+", encoding="utf-8"
                                ) as archive_file:
                                    c_archive.to_csv(archive_file, sep=";")

                                if json_check == True:
                                    c_archive.to_json(
                                        json_file + alphanumeric + "_archive.json",
                                        orient="records",
                                        compression="infer",
                                        lines=True,
                                        index=True,
                                    )
                                else:
                                    pass

                                if forwards_check is True:
                                    with open(
                                        file_forwards, "w+", encoding="utf-8"
                                    ) as forwards_file:
                                        c_forwards.to_csv(forwards_file, sep=";")

                                    if json_check == True:
                                        c_forwards.to_json(
                                            json_file + alphanumeric + "_edgelist.json",
                                            orient="records",
                                            compression="infer",
                                            lines=True,
                                            index=True,
                                        )
                                    else:
                                        pass
                                else:
                                    pass

                                messages_found = int(c_archive.To.count()) - 1
                                report_obj = object()
                                setattr(report_obj,"messages_found", messages_found)
                                setattr(report_obj,"file_archive", file_archive)
                                if chat_type == "Channel":
                                    print_shell("channel_stat", report_obj)
                                else:
                                    pvalue_count = c_archive["Display_name"].value_counts()
                                    df03 = pvalue_count.rename_axis(
                                        "unique_values"
                                    ).reset_index(name="counts")

                                    '''
                                    message_frequency_count = {}
                                    message_text = {}
                                    word_count = {}
                                    most_used_words = {}
                                    most_used_words_filtered = {}
                                    '''
                                    #message stats, top words

                                    setattr(report_obj, "poster_one", (
                                        str(df03.iloc[0]["unique_values"])
                                        + ", "
                                        + str(df03.iloc[0]["counts"])
                                        + " messages"
                                    ))
                                    setattr(report_obj, "poster_two", (
                                        str(df03.iloc[1]["unique_values"])
                                        + ", "
                                        + str(df03.iloc[2]["counts"])
                                        + " messages"
                                    ))
                                    setattr(report_obj, "poster_three", (
                                        str(df03.iloc[2]["unique_values"])
                                        + ", "
                                        + str(df03.iloc[2]["counts"])
                                        + " messages"
                                    ))
                                    setattr(report_obj, "poster_four", (
                                        str(df03.iloc[3]["unique_values"])
                                        + ", "
                                        + df03.iloc[3]["counts"]
                                        + " messages"
                                    ))
                                    setattr(report_obj, "poster_five", (
                                        str(df03.iloc[4]["unique_values"])
                                        + ", "
                                        + str(df03.iloc[4]["counts"])
                                        + " messages"
                                    ))

                                    df04 = c_archive.Display_name.unique()
                                    unique_active = len(df04)
                                    setattr(report_obj, "unique_active", unique_active)
                                    print_shell("group_stat", report_obj)

                                if reply_analysis is True:

                                    if len(replies_list) > 0:
                                        replier_value_count = c_repliers["User ID"].value_counts()
                                        replier_df = replier_value_count.rename_axis(
                                            "unique_values"
                                        ).reset_index(name="counts")

                                        repliers = object()
                                        setattr(repliers, "replier_one", (
                                            str(replier_df.iloc[0]["unique_values"])
                                            + ", "
                                            + str(replier_df.iloc[0]["counts"])
                                            + " replies"
                                        ))
                                        setattr(repliers, "replier_two", (
                                            str(replier_df.iloc[1]["unique_values"])
                                            + ", "
                                            + str(replier_df.iloc[1]["counts"])
                                            + " replies"
                                        ))
                                        setattr(repliers, "replier_three", (
                                            str(replier_df.iloc[2]["unique_values"])
                                            + ", "
                                            + str(replier_df.iloc[2]["counts"])
                                            + " replies"
                                        ))
                                        setattr(repliers, "replier_four", (
                                            str(replier_df.iloc[3]["unique_values"])
                                            + ", "
                                            + str(replier_df.iloc[3]["counts"])
                                            + " replies"
                                        ))
                                        setattr(repliers, "replier_five",  (
                                            str(replier_df.iloc[3]["counts"])
                                            + ", "
                                            + str(replier_df.iloc[4]["counts"])
                                            + " replies"
                                        ))
                                        replier_count_df = c_repliers["User ID"].unique()
                                        replier_unique = len(replier_count_df)
                                        setattr(repliers,"user_replier_list_len", len(user_replier_list))
                                        setattr(repliers, "reply_file_archive", str(reply_file_archive))
                                        setattr(repliers, "reply_memberlist_filename", str(reply_memberlist_filename))
                                        setattr(repliers,"replier_unique", str(replier_unique))
                                        print_shell("reply_stat",repliers)

                                if forwards_check is True:
                                    if forward_count >= 15:
                                        forwards_found = c_forwards.Source.count()
                                        value_count = c_forwards["Source"].value_counts()
                                        c_f_stats = value_count.rename_axis(
                                            "unique_values"
                                        ).reset_index(name="counts")
                                        report_forward = object()
                                        setattr(report_forward, "forward_one", (
                                                str(c_f_stats.iloc[0]["unique_values"])
                                                + ", "
                                                + str(c_f_stats.iloc[0]["counts"])
                                                + " forwarded messages"
                                        ))
                                        setattr(report_forward, "forward_two", (
                                                str(c_f_stats.iloc[1]["unique_values"])
                                                + ", "
                                                + str(c_f_stats.iloc[1]["counts"])
                                                + " forwarded messages"
                                        ))
                                        setattr(report_forward, "forward_three", (
                                                str(c_f_stats.iloc[2]["unique_values"])
                                                + ", "
                                                + str(c_f_stats.iloc[2]["counts"])
                                                + " forwarded messages"
                                        ))
                                        setattr(report_forward, "forward_four", (
                                                str(c_f_stats.iloc[3]["unique_values"])
                                                + ", "
                                                + str(c_f_stats.iloc[3]["counts"])
                                                + " forwarded messages"
                                        ))
                                        setattr(report_forward, "forward_five", (
                                                str(c_f_stats.iloc[4]["unique_values"])
                                                + ", "
                                                + str(c_f_stats.iloc[4]["counts"])
                                                + " forwarded messages"
                                        ))
                                        c_f_unique = c_forwards.Source.unique()
                                        setattr(report_forward, "unique_forwards", len(c_f_unique))
                                        setattr(report_forward, "edgelist_file", len(df02))
                                        setattr(report_forward, "private_count", private_count)
                                        print_shell("forwarder_stat", report_forward)
                                    else:
                                        #print("\n")
                                        color_print_green(
                                            " [!] Insufficient forwarded messages found",
                                            edgelist_file,
                                        )
                                else:
                                    pass

                    if user_check == True:
                        my_user = None
                        try:

                            user = int(t)
                            my_user = await client.get_entity(PeerUser(int(user)))

                            user_first_name = my_user.first_name
                            user_last_name = my_user.last_name
                            if user_last_name is not None:
                                user_full_name = (
                                    str(user_first_name) + " " + str(user_last_name)
                                )
                            else:
                                user_full_name = str(user_first_name)

                            if my_user.photo is not None:
                                user_photo = my_user.photo.photo_id
                            else:
                                user_photo = "None"

                            if my_user.restriction_reason is not None:
                                ios_restriction = entity.restriction_reason[0]
                                if 1 in entity.restriction_reason:
                                    android_restriction = entity.restriction_reason[1]
                                    user_restrictions = (
                                        str(ios_restriction)
                                        + ", "
                                        + str(android_restriction)
                                    )
                                else:
                                    user_restrictions = str(ios_restriction)
                            else:
                                user_restrictions = "None"
                            setattr(my_user, "user_restrictions", str(user_restrictions))
                            setattr(my_user, "user_full_name", str(user_full_name))
                            setattr(my_user, "user_photo", str(user_photo))
                            setattr(my_user, "target", t)
                            print_shell("user", my_user)

                        except ValueError:
                            pass
                        if my_user is None:
                            print(
                                Fore.GREEN
                                + " [!] "
                                + Style.RESET_ALL
                                + "User not found, this is likely because Telepathy has not encountered them yet."
                            )

                    if location_check == True:

                        location = t

                        print(
                            Fore.GREEN
                            + " [!] "
                            + Style.RESET_ALL
                            + "Searching for users near "
                            + location
                            + "\n"
                        )
                        latitude, longitude = location.split(sep=",")

                        locations_file = telepathy_file + "locations/"

                        try:
                            os.makedirs(locations_file)
                        except FileExistsError:
                            pass

                        save_file = (
                            locations_file
                            + latitude
                            + "_"
                            + longitude
                            + "_"
                            + "locations_"
                            + filetime_clean
                            + ".csv"
                        )

                        locations_list = []
                        result = await client(
                            functions.contacts.GetLocatedRequest(
                                geo_point=types.InputGeoPoint(
                                    lat=float(latitude),
                                    long=float(longitude),
                                    accuracy_radius=42,
                                ),
                                self_expires=42,
                            )
                        )

                        # progress bar?

                        for user in result.updates[0].peers:
                            try:
                                user_df = pd.DataFrame(
                                    locations_list, columns=["User_ID", "Distance"]
                                )
                                if hasattr(user, "peer"):
                                    ID = user.peer.user_id
                                else:
                                    pass
                                if hasattr(user, "distance"):
                                    distance = user.distance
                                else:
                                    pass

                                locations_list.append([ID, distance])

                            except:
                                pass

                        distance_obj = object()
                        setattr(distance_obj, "d500", 0)
                        setattr(distance_obj, "d1000", 0)
                        setattr(distance_obj, "d2000", 0)
                        setattr(distance_obj, "d3000", 0)

                        for account, distance in user_df.itertuples(index=False):
                            account = int(account)
                            my_user = await client.get_entity(PeerUser(account))
                            user_id = my_user.id
                            name = my_user.first_name
                            distance = int(distance)

                            if distance == 500:
                                distance_obj.d500 += 1
                            elif distance == 1000:
                                distance_obj.d1000 += 1
                            elif distance == 2000:
                                distance_obj.d2000 += 1
                            elif distance == 3000:
                                distance_obj.d3000 += 1

                        with open(
                            save_file, "w+", encoding="utf-8"
                        ) as f:  # could one day append, including access time to differentiate
                            user_df.to_csv(f, sep=";", index=False)

                        setattr(distance_obj, "save_file", save_file)
                        setattr(distance_obj, "total", total)
                        total = len(locations_list)
                        print_shell("location_report",distance_obj)
                        # can also do the same for channels with similar output file to users
                        # may one day add trilateration to find users closest to exact point
                        
    with client:
        client.loop.run_until_complete(main())

if __name__ == "__main__":
    cli()

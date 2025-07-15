import argparse
import os
import re
import time

from genericpath import isfile
from pymediainfo import MediaInfo

# The download path for a completed file must contain the word "complete"
# python3 -m pip install --upgrade pip setuptools wheel
# sudo apt install python3-pip -y && sudo apt-get install -y libmediainfo-dev && pip3 install pymediainfo

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
path = ""
file_path_passed = ""
ignored_folder_names = []

# Whether to move the file to a new folder or not
move_to_folder = True

# How long to wait before renaming the file in minutes
# This is to make sure only stalled upgrade files are renamed.
required_wait_time = 20

# The maximum time to wait before renaming the file in minutes.
max_wait_time = 60

# The accepted file extensions
allowed_extensions = [".mkv", ".mp4"]


parser = argparse.ArgumentParser(
    description="Renames scene anime video files, adding metadata to the filename that the releaser left out."
)
parser.add_argument(
    "-p",
    "--path",
    help="The path to the directory to search for video files recursively.",
    required=False,
)
parser.add_argument("-f", "--file", help="File to rename", required=False)
args = parser.parse_args()
if args.path:
    path = args.path
if args.file:
    file_path_passed = args.file
if not path and not file_path_passed:
    print("No file or download directory specified. Exiting.")
    exit()


class Audio_Track:
    def __init__(self, codec, language, channels):
        self.codec = codec
        self.language = language
        self.channels = channels


class Video_Track:
    def __init__(self, resolution, bit_depth, codec):
        self.resolution = resolution
        self.bit_depth = bit_depth
        self.codec = codec


class Subtitle_Track:
    def __init__(self, language, title, codec):
        self.language = language
        self.title = title
        self.codec = codec


class Video_File:
    def __init__(self, video_track, audio_tracks, subtitle_tracks):
        self.video_track = video_track
        self.audio_tracks = audio_tracks
        self.subtitle_tracks = subtitle_tracks


# get age of file and return in minutes based on modification time
def get_modiciation_age(file):
    return int(time.time() - os.path.getmtime(file)) / 60


# get age of file and return in minutes based on creation time
def get_creation_age(file):
    return int(time.time() - os.path.getctime(file)) / 60


# get metadata from video file using pymediainfo
def get_metadata(file):
    video_track = None
    audio_tracks = []
    subtitle_tracks = []
    media_info = MediaInfo.parse(file)
    for track in media_info.tracks:
        if track.track_type == "Video" and not video_track:
            video_track = Video_Track(
                str(track.height) + "p",
                str(track.bit_depth) + "bit",
                track.commercial_name,
            )
        elif track.track_type == "Audio":
            lang_track = ""
            if track.language:
                lang_track = str(track.language).upper()
            elif track.title and re.search(
                r"(English|\bENG?\b)", track.title, re.IGNORECASE
            ):
                lang_track = "EN"
            elif track.title and re.search(
                r"(Japanese|\bJPN?\b)", track.title, re.IGNORECASE
            ):
                lang_track = "JP"
            audio_tracks.append(
                Audio_Track(track.commercial_name, lang_track, track.channel_s)
            )
        elif track.track_type == "Text":
            subtitle_track = Subtitle_Track(
                str(track.language).upper(), track.title, track.commercial_name
            )
            subtitle_tracks.append(subtitle_track)
    if video_track and audio_tracks and subtitle_tracks:
        return Video_File(video_track, audio_tracks, subtitle_tracks)
    else:
        return None


# Removes any folder names in the ignored_folders
def remove_ignored_folders(dirs):
    if len(ignored_folder_names) != 0:
        dirs[:] = [d for d in dirs if d not in ignored_folder_names]


# remove duplicates elements from the passed in list
def remove_duplicates(items):
    return list(dict.fromkeys(items))


# Remove hidden folders from the list
def remove_hidden_folders(root, dirs):
    for folder in dirs[:]:
        if (folder.startswith(".") or folder.startswith("_")) and os.path.isdir(
            os.path.join(root, folder)
        ):
            dirs.remove(folder)


# remove any directories that start with _
def remove_underscores(dirs):
    for dir in dirs[:]:
        if dir.startswith("_"):
            dirs.remove(dir)


# Removes hidden files
def remove_hidden_files(files, root):
    for file in files[:]:
        if file.startswith("."):
            files.remove(file)


# Retrieves the file extension on the passed file
def get_file_extension(file):
    return os.path.splitext(file)[1]


print("Starting...\n")
if not path and file_path_passed:
    path = os.path.dirname(file_path_passed)

for root, dirs, files in os.walk(path, topdown=True):
    if "/complete" not in root:
        continue

    base_name = os.path.basename(root)

    # check if folder naame is in ignored_folders
    if base_name in ignored_folder_names:
        continue

    print("\n" + root)

    remove_ignored_folders(dirs)
    remove_underscores(dirs)
    remove_hidden_folders(root, dirs)
    remove_hidden_files(files, root)

    # print(dirs)
    # print(files)

    for file in files:
        extension = get_file_extension(file)

        if extension not in allowed_extensions:
            continue
        if file.startswith(".") or file.startswith("_"):
            continue

        try:
            creation_time = get_creation_age(os.path.join(root, file))
            modification_time = get_modiciation_age(os.path.join(root, file))

            # Check if the file is old enough to be renamed
            allowed_to_modify = (
                (creation_time and modification_time)
                and (
                    creation_time >= required_wait_time
                    and modification_time >= required_wait_time
                )
                and (
                    creation_time <= max_wait_time
                    and modification_time <= max_wait_time
                )
            )

            if not allowed_to_modify:
                print(f"\n\tfolder: {root}")
                print(f"\tcreation time: {creation_time}")
                print(f"\tmodification time: {modification_time}")
                print(
                    "\t"
                    + file
                    + " is too young, please wait until "
                    + str(required_wait_time)
                    + " minutes."
                )
                continue

            try:
                if file_path_passed and os.path.basename(file_path_passed) != file:
                    continue

                file_path = os.path.join(root, file)

                file_directory = os.path.dirname(file_path)
                file_directory_base = os.path.basename(file_directory)

                file_name = os.path.basename(file_path)
                file_extension = os.path.splitext(file_name)[1]
                file_name_no_extension = os.path.splitext(file_name)[0]

                print("\t" + file_name)
                metadata = get_metadata(file_path)
                rename = file_name_no_extension

                # Search for Blu-Ray keywords
                blu_ray_keyword_search = re.search(
                    r"(\b(?:(Blu-?Ray|BDMux|BD(?!$))|(B[DR]Rip))(?:\b|$|[ .])|(Web-?Rip|WEBMux)|(\b(WEB[-_. ]?DL|WebHD|[. ]WEB[. ](?:[xh]26[45]|DDP?5[. ]1)|[. ](?-i:WEB)$|\d+0p(?:WEB-DLMux|\b\s\/\sWEB\s\/\s\b))))",
                    file_directory_base,
                    re.IGNORECASE,
                )
                blu_ray_keywords = ""
                if blu_ray_keyword_search:
                    blu_ray_keywords = blu_ray_keyword_search.group(0)

                if metadata:
                    add = ""

                    # Search and add video codec
                    if not re.search(metadata.video_track.codec, rename, re.IGNORECASE):
                        print("\t\tVideo Codec: " + metadata.video_track.codec)
                        if metadata.video_track.codec in [
                            "HEVC",
                            "H.265",
                            "x265",
                        ]:
                            codec_regex = r"(\bHEVC|H\.265|x265\b)"
                        elif metadata.video_track.codec in [
                            "AVC",
                            "H.264",
                            "x264",
                        ]:
                            codec_regex = r"(\bAVC|H\.264|x264\b)"
                        else:
                            codec_regex = re.escape(metadata.video_track.codec)

                        if not re.search(codec_regex, file_name, re.IGNORECASE):
                            add += " " + metadata.video_track.codec

                    # Search and add video resolution
                    if not re.search(
                        metadata.video_track.resolution, rename, re.IGNORECASE
                    ):
                        print(
                            "\t\tVideo Resolution: " + metadata.video_track.resolution
                        )
                        if metadata.video_track.resolution in [
                            "480p",
                            "576p",
                            "720p",
                            "1080i",
                            "1080p",
                            "2160p",
                            "4320p",
                        ]:
                            if not re.search(
                                rf"(\b{metadata.video_track.resolution}?\b)",
                                file_name,
                                re.IGNORECASE,
                            ):
                                add += " " + metadata.video_track.resolution
                        else:
                            add += " " + metadata.video_track.resolution

                    # Search and add video bit depth
                    if not re.search(
                        metadata.video_track.bit_depth, rename, re.IGNORECASE
                    ):
                        print("\t\tVideo Bit Depth: " + metadata.video_track.bit_depth)
                        if metadata.video_track.bit_depth in ["8bit", "10bit"]:
                            if not re.search(
                                r"(\b(8|10)[-_. ]?bit\b)",
                                file_name,
                                re.IGNORECASE,
                            ):
                                add += " " + metadata.video_track.bit_depth
                        else:
                            add += " " + metadata.video_track.bit_depth

                    audio_track_string = ""
                    audio_codecs = []
                    audio_languages = []

                    # Combine all the audio languages into a single string
                    for audio_track in metadata.audio_tracks:
                        if audio_track.codec not in audio_codecs:
                            audio_codecs.append(audio_track.codec)
                        if audio_track.language not in audio_languages:
                            audio_languages.append(audio_track.language)
                            if not audio_track_string:
                                print("\t\tAudio Language: " + audio_track.language)
                                audio_track_string += audio_track.language
                            else:
                                print("\t\tAudio Language: " + audio_track.language)
                                audio_track_string += "+" + audio_track.language

                    excluded_languages = ["mul", "und", "zxx", "qaa", "mis", ""]

                    # Remove any excluded languages from the audio list
                    audio_languages = [
                        language
                        for language in audio_languages
                        if language.lower().strip() not in excluded_languages
                    ]

                    # Add the audio languages to the file name
                    if audio_codecs:
                        add += " "
                        add += " ".join(
                            [
                                codec
                                for codec in audio_codecs
                                if not re.search(codec, rename, re.IGNORECASE)
                            ]
                        )
                        print("\t\tAudio Codec: " + ", ".join(audio_codecs))

                    dual_audio_keyword_search = re.search(
                        r"(dual[ ._-]?(audio|dub|dubbed)|\sdual\s|EN\+JA|JA\+EN|\[eng?,?(\s+)?jpn?\]|\[jpn?,?(\s+)?eng?\])",
                        file_name,
                        re.IGNORECASE,
                    )
                    if (
                        audio_track_string
                        and not re.search(
                            re.escape(audio_track_string), rename, re.IGNORECASE
                        )
                        and not dual_audio_keyword_search
                    ):
                        print("\t\tAudio Languages Combined: " + audio_track_string)
                        if (
                            re.search(
                                r"(EN\+JA|JA\+EN)",
                                audio_track_string,
                                re.IGNORECASE,
                            )
                        ) and not dual_audio_keyword_search:
                            add += " " + audio_track_string
                        else:
                            add += " " + audio_track_string

                    # Add dual audio keyword if there are only two audio tracks
                    if len(audio_languages) < 3 and not dual_audio_keyword_search:
                        if audio_track_string and (
                            re.search(
                                r"(EN\+JA|JA\+EN)",
                                audio_track_string,
                                re.IGNORECASE,
                            )
                        ):
                            add += " Dual Audio"
                    # Add multi audio keyword if there are more than two audio tracks
                    elif len(audio_languages) >= 3:
                        if not re.search(
                            r"(multi[ ._-]?audio|multi[ ._-]?dub)",
                            file_name,
                            re.IGNORECASE,
                        ):
                            add += " Multi Audio"

                    # Add the blu-ray keyword to the file name if there are any PGS subtitles
                    if metadata.subtitle_tracks:
                        for track in metadata.subtitle_tracks:
                            if track.codec:
                                print("\t\tSubtitle Codec: " + track.codec)
                            if track.codec == "PGS" and not re.search(
                                r"\b(?:(Blu-?Ray|BDMux|BD(?!$))|(B[DR]Rip))(?:\b|$|[ .])",
                                file_name,
                                re.IGNORECASE,
                            ):
                                add += " Blu-Ray"
                                break

                    if blu_ray_keywords and not re.search(
                        blu_ray_keywords, file_name, re.IGNORECASE
                    ):
                        add += " " + blu_ray_keywords

                    if add or "_" in rename:
                        # replace periods with spaces
                        rename = rename.replace(".", " ")

                        # replace underscores with spaces
                        rename = rename.replace("_", " ")

                        # replace all punctuation with spaces
                        rename = re.sub(r"[^\w\s\[\]\(\)\{\}-]", " ", rename)

                        # remove multiple spaces
                        rename = re.sub(" +", " ", rename).strip()

                        if add:
                            add = "[" + add.strip() + "]"
                            rename += " " + add

                        # add the extension
                        rename += file_extension

                        # check that the new name is different from the old name
                        if rename.strip().lower() != file_name.strip().lower():
                            print("\tRenaming file")
                            print("\t\tFROM: " + file_name + "\n\t\tTO:   " + rename)

                            rename_path = os.path.join(file_directory, rename)
                            os.rename(file_path, rename_path)

                            if os.path.isfile(rename_path):
                                print("\t\t\tFile Successfully Renamed")
                            else:
                                print("\t\t\tFile Rename Failed")

                            # Move the lone file to a new folder
                            if move_to_folder and file_directory_base == "downloads":
                                new_folder_old_name = os.path.join(
                                    file_directory, file_name
                                )
                                if not os.path.exists(new_folder_old_name):
                                    print("\t\tCreating folder")
                                    os.mkdir(new_folder_old_name)
                                if os.path.exists(new_folder_old_name):
                                    print("\t\tMoving file")
                                    if not os.path.isfile(
                                        os.path.join(new_folder_old_name, rename)
                                    ):
                                        os.rename(
                                            rename_path,
                                            os.path.join(new_folder_old_name, rename),
                                        )
                                        if os.path.isfile(
                                            os.path.join(new_folder_old_name, rename)
                                        ):
                                            print("\t\tFile Successfully Moved")
                                        else:
                                            print("\t\tFile Move Failed")
                                    else:
                                        print("\t\tFile Already Exists")
                                else:
                                    print("\t\tFile Move Failed")
                else:
                    print("\t\tNo metadata")
            except Exception as e:
                print("\t\tError: " + str(e))
                continue
        except Exception as e:
            print("Error: " + str(e))
            continue
print("\nFinished.")

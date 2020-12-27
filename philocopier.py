#!/usr/bin/python3
from re import compile, Pattern, Match, sub
from datetime import timedelta
import requests
from requests import RequestException
from bs4 import BeautifulSoup
import json
import time
import sys

#TODO:
# - Find/check twibooru upload route (seriously why the fuck would you opt to use the old API fuck u)
# - Write unit tests
# -! Check tag overlap for successful reverse search

# Matches a domain, ignoring http/https and the trailing /
domain_pattern: Pattern = compile(r"^(?:https?:\/\/)?(.+?\.\w+?)\/?$")

# Matches an image link, such as >>123, >>123t, or >>123p. The leftmost non-capturing group
# is there to handle weird edge cases
image_link_pattern: Pattern = compile(r"(?:^|[^=]{1,2}|[^=]=|^=)>>([0-9]+)(t|p|s?)")

# Matches a relative link, which are done like: "this":http://example.com
relative_link_pattern: Pattern = compile(r'"(.+)":(\/.+) ?')

# Matches an api key
api_key_pattern = compile(r"^(.{20})$")

# Matches an integer
source_filter_pattern = compile(r"^d+$")

# Maximum number of retries once the longest timeout has been reached (some images cannot be uploaded)
# With the default parameters, this represents ~3000 seconds on one attempt. It's a fair assumption
# that it will not work
max_attempts_at_max_delay = 2

# Retry delays, in seconds
init_retry_delay = 0.25
max_retry_delay = 256

per_page = 50
timeout_seconds = 20

class Config(object):
    target_api_key: str
    source_api_key: str
    source_booru: str
    source_booru_short: str
    target_booru: str
    reverse_search: bool
    tag_mapping: dict
    source_filter_id: int

    def __init__(self, source_booru, source_api_key, target_api_key, target_booru, use_reverse = True, tag_mapping = None, source_filter_id = None):
        self.tag_mapping = tag_mapping
        self.source_booru = source_booru
        self.source_api_key = source_api_key
        self.target_api_key = target_api_key
        self.target_booru = target_booru
        self.reverse_search = use_reverse
        self.source_filter_id = source_filter_id

        # Strip the domain name
        self.source_booru_short = source_booru[:source_booru.rfind(".")]

# Returns true if reverse search finds something
# If a server-side error occurs, we treat that as "no results"
def reverse_search(booru: str, api_key: str, image: dict):
    # For debugging
    #return True
    img_url = image["view_url"]
    j = {"url": img_url, "distance": 0.1, "key":api_key}
    url = f"https://{booru}/api/v1/json/search/reverse?key={api_key}"
    try:
        r = requests.post(url, data=j, timeout=timeout_seconds)
        images = r.json()
        if type(images) == dict and "total" in images:
            return images["total"]
        else:
            return 0

    # Probably a server-side error
    except json.JSONDecodeError:
        return 0
    except RequestException as e:
        print(f"RequestException occurred: {e}")
        return 0

# Does nothing for now, ignore
def get_svg_url(booru, image_id) -> str:
    image_url = "https://{booru}/images/{image_id}"


# To use in a GET request
def get_search_query_url(booru: str, api_key: str, query: str, page: int, filter_id: int):
    # Twibooru uses the old api. I don't know of other sites that do
    req = None
    if booru == "twibooru.org":
        req = f"https://{booru}/search.json?key={api_key}&page={page}&per_page={per_page}&q={query}&sf=created_at&sd=asc"
    else:
        req = f"https://{booru}/api/v1/json/search/images?key={api_key}&page={page}&per_page={per_page}&q={query}&sf=created_at&sd=asc"

    if filter_id is not None:
        req = req + f"&{filter_id}"

# To use in a POST request
def get_upload_url(booru: str, api_key: str):
    if booru == "twibooru.org":
        raise NotImplementedError # Twibooru's documentation is shit, and I have better things to do
    else:
        return f"https://{booru}/api/v1/json/images?key={api_key}"

# Pattern needs to have one capturing group
def get_input_with_pattern(r: Pattern, prompt_text: str, error_text: str = "Invalid input"):
    while True:
        user_input = input(prompt_text)
        match = r.match(user_input)
        if match:
            return match[1]
        else:
            print(error_text)

# To be used only with match objects from image_link_pattern
def replace_image_link(match: Match, booru: str):
    return f"\"==>>{match[1]}{match[2]}==\":https://{booru}/images/{match[1]}"

def replace_relative_link(match: Match, booru: str):
    return f"\"{match[1]}\":https://{booru}{match[2]}"

def get_imgs_from_config(config: Config, query: str, page: int):
    return get_search_query_images( booru     = config.source_booru,\
                                    api_key   = config.source_api_key,\
                                    filter_id = config.source_filter_id,\
                                    query     = query,\
                                    page      = page)

def get_search_query_images(booru: str, api_key: str, query: str, page: int, filter_id = None):
    query_url: str = get_search_query_url(booru, api_key, query, page, filter_id)
    try:
        response = requests.get(query_url, timeout=timeout_seconds)
        images_received = response.json()
        images = images_received
        # Adapts an image from the old api to the new one
        # This doesn't adapt *all* the changes, just the ones that are relevant
        if booru == "twibooru.org":
            images["images"] = images["search"]
            del images["search"]
            for image in images["images"]:
                image["tags"] = image["tags"].split(", ")
        
        return images
    except RequestException as e:
        print(f"RequestException occurred: {e}")
        return None

        
def upload_image(image: dict, booru: str, api_key: str):
    upload_url = get_upload_url(booru, api_key)

    tag_string = ", ".join(image["tags"])
    image_to_upload = {"description": image["description"], "source_url": image["source_url"], "tag_input": tag_string}
    upload_image_body = {"image": image_to_upload, "url": image["view_url"]}

    try:
        r = requests.post(upload_url, json=upload_image_body, timeout=timeout_seconds)
        if r.status_code == requests.codes.ok:
            return True
        else:
            print(f"Error uploading image ({r.status_code})")
            if r.status_code == requests.codes.bad_request:
                return True # Lazy hack; technically, the upload did succeed, since the file is already on the server
                print("This is because the hash is already present on the server")
            return False
    except RequestException as e:
        print(f"RequestException occurred: {e}")
        return False

version = "1.0"
# God I hate python. Just let me have a unified constructor
def dict_to_config(d) -> Config:
        target_api_key = d.get("target_api_key")
        if target_api_key is None:
            raise ValueError("target_api_key is mandatory")

        source_api_key = d.get("source_api_key")
        if source_api_key is None:
            raise ValueError("source_api_key is mandatory")

        source_booru   = d.get("source_booru")
        if source_booru is None:
            raise ValueError("source_booru is mandatory")

        target_booru   = d.get("target_booru")
        if target_booru is None:
            raise ValueError("target_booru is mandatory")

        reverse_search = d.get("reverse_search", True)
        if type(reverse_search) != bool:
            raise ValueError("reverse_search has to be a boolean value")

        tag_mapping    = d.get("tag_mapping")
        if tag_mapping is not None and type(tag_mapping) != dict:
            raise ValueError("tag_mapping has to be an object")

        source_filter_id = d.get("source_filter_id") # Allowed to be None

        return Config(  source_booru=source_booru, source_api_key=source_api_key,\
                        target_api_key, target_booru, reverse_search, tag_mapping,\
                        source_filter_id = source_filter_id)



def get_config():
    if len(sys.argv) > 1:
        config_path = "config.json" # yeah, can't be assed
        with open(config_path) as config_file:
            config_dict = json.load(config_file)
            config = dict_to_config(config_dict)

        search_query = " ".join(sys.argv[1:])
    else:
        print(f"Pylomena copier v{version}")
        print()
        print("Ensure your filter are set correctly on the source booru. "\
            "The active filter will be used when copying images.")
        print("API keys can be found on the Account page")
        print()

        # Get booru info
        source_booru = get_input_with_pattern(domain_pattern, "Enter source booru url: ")
        source_api_key = get_input_with_pattern(api_key_pattern, "Enter source booru API key: ")
        target_booru = get_input_with_pattern(domain_pattern, "Enter target booru url: ")
        target_api_key = get_input_with_pattern(api_key_pattern, "Enter target booru API key: ")

        # Get query
        print("Enter query to copy from the source booru to the target booru. Any query that can be made on the site will work.")
        search_query = input("Query: ").strip()

        search_images = get_search_query_images(\
                source_booru, source_api_key,\
                search_query, page = 1) # page is irrelevant for this, we just want the count

        if search_images is None or len(search_images["images"]) == 0:
            print("This query has no images! Double-check the query and try again.")
            raise ValueError("No images found")
    
        total_images = search_images["total"]

        print(f"There are {total_images} images in this query")
        print(f"Ensure the query and image count are correct! If not, Ctrl-C to exit.")
        use_reverse = True
        try:
            r = input("Use reverse search? [Y/n]")
            if r == "n": 
                use_reverse = False
        except EOFError:
            pass

        config = Config(source_booru, source_api_key, target_api_key, target_booru, use_reverse,\
                        source_filter_id = None) # Honestly, I should have abandoned the stdin mode when I added configs

    return config, search_query

def change_tags(tags: list, config: Config) -> list:
    if config.tag_mapping is not None:
        result = []
        for tag in tags:
            if tag in config.tag_mapping:
                replacement = config.tag_mapping[tag]
                if type(replacement) == list:
                    for rep in replacement:
                        result.append(rep)
                elif replacement is not None:
                    result.append(replacement)
                # if the replacement is none, then just delete the dag
            else:
                result.append(tag) # Don't change tag
    else:
        result = tags

    result.append(f"{config.source_booru_short} import")
    return result

def change_description(description: str, config: Config):
    new_description = sub(image_link_pattern, lambda m: replace_image_link(m, config.source_booru), description)
    new_description = sub(relative_link_pattern, lambda m: replace_relative_link(m, config.source_booru), new_description)
    return new_description

def main():
    try:
        config, search_query = get_config()

        current_page = 1
        current_image = 0
        current_retry_delay = init_retry_delay
        search_images = get_imgs_from_config(config, search_query, current_page)
                        
                        

        total_images = search_images["total"]
        while len(search_images["images"]) > 0:
            for image in search_images["images"]:
                current_image += 1
                current_retry_delay = init_retry_delay
                image["description"] = change_description(image["description"], config)
                image["tags"] = change_tags(image["tags"], config)

                image_id = image["id"]
                print(f"Uploading image {current_image}/{total_images} ({image_id})")

                if config.reverse_search:
                    print("Reverse searching…")
                    rev = reverse_search(config.target_booru, config.target_api_key, image)
                    if rev > 0:
                        print(f"Reverse search found {rev} matching images (skipping)")
                        continue
                    else:
                        print("No results found, uploading…")

                attempts_at_max_delay = 0
                while attempts_at_max_delay < max_attempts_at_max_delay:

                    # Upload succeeded
                    if upload_image(image, config.target_booru, config.target_api_key):
                        break
                    # Upload failed
                    else:
                        print(f"Retrying in {current_retry_delay} seconds…")
                        time.sleep(current_retry_delay)

                        if current_retry_delay < max_retry_delay:
                            current_retry_delay *= 2
                        else:
                            current_retry_delay = max_retry_delay
                            attempts_at_max_delay += 1

                if attempts_at_max_delay == max_attempts_at_max_delay:
                    print("Max attempts reached; moving onto next image.")

                # To avoid sending too many requests
                time.sleep(init_retry_delay)

            # Load the next page
            current_retry_delay = init_retry_delay
            current_page += 1

            search_images = None
            while search_images is None:
                search_images = get_imgs_from_config(config, search_query, current_page)
                time.sleep(current_retry_delay)
                if current_retry_delay < max_retry_delay:
                    current_retry_delay *= 2



    except KeyboardInterrupt:
        return
    




if __name__ == "__main__":
    main()

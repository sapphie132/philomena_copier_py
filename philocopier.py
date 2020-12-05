#!/usr/bin/python3
from re import compile, Pattern, Match, sub
from datetime import timedelta
import requests
import json
import time

#TODO:
# - Find/check twibooru upload route (seriously why the fuck would you opt to use the old API fuck u)
# - Write unit tests
# - Add exception handling
# -! Check tag overlap for successful reverse search

# Matches a domain, ignoring http/https and the trailing /
domain_pattern: Pattern = compile(r"^(?:https?:\/\/)?(.+?\.\w+?)\/?$")

# Matches an image link, such as >>123, >>123t, or >>123p. The leftmost non-capturing group
# is there to handle weird edge cases
image_link_pattern: Pattern = compile(r"(?:^|[^=]{1,2}|[^=]=|^=)>>([0-9]+)(t|p?)")

# Matches a relative link, which are done like: "this":http://example.com
relative_link_pattern: Pattern = compile(r'"(.+)":(\/.+) ?')

# Matches an api key
api_key_pattern = compile(r"^(.{20})$")

# Maximum number of retries once the longest timeout has been reached (some images cannot be uploaded)
# With the default parameters, this represents ~3000 seconds on one attempt. It's a fair assumption
# that it will not work
max_attempts_at_max_delay = 2

# Retry delays, in seconds
init_retry_delay = 0.25
max_retry_delay = 512

per_page = 50

# Returns true if reverse search finds something
def reverse_search(booru: str, api_key: str, image: dict):
    # For debugging
    #return True
    img_url = image["view_url"]
    j = {"url": img_url, "distance": 0.1, "key":api_key}
    url = f"https://{booru}/api/v1/json/search/reverse?key={api_key}"
    r = requests.post(url, data=j)
    try:
        images = r.json()
        if type(images) == dict and "total" in images:
            return images["total"]
        else:
            return 0

    # Probably a server-side error
    except json.JSONDecodeError:
        return 0


# To use in a GET request
def get_search_query_url(booru: str, api_key: str, query: str, page: int):
    # Twibooru uses the old api. I don't know of other sites that do
    if booru == "twibooru.org":
        return f"https://{booru}/search.json?key={api_key}&page={page}&per_page={per_page}&q={query}&sf=created_at&sd=asc"
    else:
        return f"https://{booru}/api/v1/json/search/images?key={api_key}&page={page}&per_page={per_page}&q={query}&sf=created_at&sd=asc"

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

def get_search_query_images(booru: str, api_key: str, query: str, page: int):
    query_url: str = get_search_query_url(booru, api_key, query, page)
    response = requests.get(query_url)
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

        
def upload_image(image: dict, booru: str, api_key: str):
    upload_url = get_upload_url(booru, api_key)

    tag_string = ", ".join(image["tags"])
    image_to_upload = {"description": image["description"], "source_url": image["source_url"], "tag_input": tag_string}
    upload_image_body = {"image": image_to_upload, "url": image["view_url"]}

    r = requests.post(upload_url, json=upload_image_body)
    if r.status_code == requests.codes.ok:
        return True
        print(f"Error uploading image ({r.status_code})(this could be because the image is already uploaded)")
    else:
        print(f"Error uploading image ({r.status_code})")
        if r.status_code == requests.codes.bad_request:
            return True # Lazy hack; technically, the upload did succeed, since the file is already on the server
            print("(This could be because the image is already present on the target site—duplicate hash)")
        return False

version = "1.0"

def main():
    try:
        print(f"Pylomena copier v{version}")
        print()
        print("Ensure your filter are set correctly on the source booru. "\
            "The active filter will be used when copying images.")
        print("API keys can be found on the Account page")
        print()

        # Get booru info
        source_booru = get_input_with_pattern(domain_pattern, "Enter source booru url: ")
        source_api_key = get_input_with_pattern(api_key_pattern, "Enter source booru API key: ")
        source_booru_short = source_booru[:source_booru.rfind(".")]
        target_booru = get_input_with_pattern(domain_pattern, "Enter target booru url: ")
        target_api_key = get_input_with_pattern(api_key_pattern, "Enter target booru API key: ")

        # Get query
        print("Enter query to copy from the source booru to the target booru. Any query that can be made on the site will work.")
        search_query = input("Query: ").strip()
    
        current_page = 1
        search_images = get_search_query_images(source_booru, source_api_key, search_query, current_page)
        if len(search_images) == 0:
            print("This query has no images! Double-check the query and try again.")
            return
    
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
        current_image = 0
        current_retry_delay = init_retry_delay

        while len(search_images["images"]) > 0:
            for image in search_images["images"]:
                current_image += 1
                current_retry_delay = init_retry_delay
                new_description = sub(image_link_pattern, lambda m: replace_image_link(m, source_booru), image["description"])
                new_description = sub(relative_link_pattern, lambda m: replace_relative_link(m, source_booru), new_description)
                image["description"] = new_description
                image["tags"].append(f"{source_booru_short} import")

                image_id = image["id"]
                print(f"Uploading image {current_image}/{total_images} ({image_id})")

                if use_reverse:
                    print("Reverse searching…")
                    rev = reverse_search(target_booru, target_api_key, image)
                    if rev > 0:
                        print(f"Reverse search found {rev} matching images (skipping)")
                        continue

                attempts_at_max_delay = 0
                while attempts_at_max_delay < max_attempts_at_max_delay:

                    # Upload succeeded
                    if upload_image(image, target_booru, target_api_key):
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
                search_images = get_search_query_images(source_booru, source_api_key, search_query, current_page)
                time.sleep(current_retry_delay)
                if current_retry_delay < max_retry_delay:
                    current_retry_delay *= 2

                
            


    except KeyboardInterrupt:
        return
    




if __name__ == "__main__":
    main()

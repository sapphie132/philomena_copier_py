# Philomena Copier
Copies images from one Philomena booru to another

Requires an account on both the source and target booru to use API keys.

Uses [Python 3.8 or higher](https://www.python.org/downloads/) (But 3.6+ might work as well).

## Notes

- The filter you have set on the source booru will be used when copying. Anything hidden will not be copied.
- Unlike its predecessor, this version actually checks by reverse search whether or not an
  image has been uploaded already. 
  This behaviour can be disabled (and doing so will speed up the copying process).
- Any query works, even `my:upvotes`, `my:uploads`, `my:watched`, etc.

## Tips

To speed up inputting the booru urls and keys, you can type the following (replacing placeholders) and copy-paste it into the terminal. It will input each line in order automatically. Make sure there is a newline at the end or the last one won't enter automatically.

```
<sourceBooruUrl>
<sourceApiKey>
<targetBooruUrl>
<targetApiKey>
<use reverse search?>

```
## Config file

Alternatively, you can pass your query as a parameter, in which case the script will automatically search for `config.json`. 
Example of a (fully populated) config:
```json
{
  "target_booru": "ponybooru.org",
  "source_booru": "derpibooru.org",
  "source_api_key": "123456789abcdefghijk",
  "target_api_key": "123456789abcdefghijk", 
  "tag_mapping": {"adventure in the comments": null, 
                  "princess celestia": ["princess celestia", "best pony"],
                  "derpibooru exclusive":"ironic tag"},
  "reverse_search": true
}
```
`tag_mapping` is optional, but can be useful if you replace tags (either by an individual tag, or by an array of tags), or remove them (by setting it to `null` in the file). The above example removes the tag `adventure in the comments`, replaces `princess celestia` with `princess celestia` and `best pony` (i.e., adds `best pony` to any Celestia pic). You can figure out what the last entry does.
`reverse_search` is also optional, but defaults to `true`.

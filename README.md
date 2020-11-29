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

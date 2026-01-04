#!/bin/bash

# usage: ./getIssueData.sh <host> <repo> <issue_id>
HOST=$1
REPO=$2
ID=$3

# Fetch and process
issueBody=$(curl -s "https://$HOST/api/v1/repos/$REPO/issues/$ID" | jq -r '
  .body 
  | split("\r\n") | map(split("\n")) | flatten  # Handle mixed Windows/Linux newlines
  | map(select(length > 0))                     # Remove empty lines
  | reduce .[] as $line (
      {current_key: null}; 
      
      # 1. Check if line starts with "Key: "
      if ($line | test(": ")) then
        ($line | index(": ")) as $idx |
        ($line[:$idx]) as $k |
        ($line[$idx+2:]) as $v |
        .current_key = $k |
        
        # SPECIAL HANDLING: If key is "Social links", start an array
        if $k == "Social links" then
            if ($v | length > 0) then .[$k] = [$v] else .[$k] = [] end
        else
            .[$k] = $v
        end

      # 2. If it is a continuation line (no key found)
      elif .current_key == "Social links" then
        .[.current_key] += [$line]   # Append to array for Social links
      elif .current_key then
        .[.current_key] += "\n" + $line # Append to string for others (Notes, etc)
      else
        .
      end
    )
  | del(.current_key)
  ')
communityName=$(echo $issueBody | jq -r '."Community name"')
icon=$(echo $issueBody | jq  -r '."Icon URL"')
lightningTips=$(echo $issueBody | jq -r '.Lightning')
contact=$(echo $issueBody | jq -r '."Social links"')
description=$(echo $issueBody | jq -r '.Notes')
cat << EOF
{
  "OSM_ID":"",
  "NAME": "$communityName",
  "AREA_TYPE": "",
  "CONTINENT": "",
  "ICON":"$icon",
  "LIGHTNING_TIPS":"$lightningTips",
  "CONTACT":$contact,
  "DESCRIPTION":"$description",
  "ORGANIZATION":""
}
EOF


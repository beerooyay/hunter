#!/bin/sh
set -eu
cd "$(dirname "$0")"
cc -std=c11 -O3 -Wall -Wextra independent_bridges.c -o independent_bridges
cc -std=c11 -O3 -Wall -Wextra difference_bridges.c -o difference_bridges
cc -std=c11 -O3 -Wall -Wextra three_way_full.c -o three_way_full
cc -std=c11 -O3 -Wall -Wextra independent_words.c -o independent_words
python3 generate_results.py
for k in 2 3 4 5 6 7; do
  ./independent_words "$k" > /tmp/pfc_words_"${k}"_"$$".txt
  cmp /tmp/pfc_words_"${k}"_"$$".txt words_"$k".txt
  rm -f /tmp/pfc_words_"${k}"_"$$".txt
done
python3 -m unittest discover -p 'test_v02.py' -v
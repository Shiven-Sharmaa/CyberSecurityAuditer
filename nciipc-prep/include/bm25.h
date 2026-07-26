#pragma once
#include "chunker.h"
#include <string>
#include <vector>
#include <unordered_map>
using namespace std;

struct Index {
    unordered_map<string,
        vector<pair<int,float>>> postings;
    vector<int> doc_lengths;
    float avg_dl = 0.0f;
    int N = 0;
};

void build_index(Index& idx, const vector<Chunk>& chunks);
vector<pair<int,float>> query_bm25(const Index& idx,
                                   const string& q,
                                   int k = 50);
void save_index(const Index& idx, const string& path);
#include "bm25.h"
#include <cmath>
#include <algorithm>
#include <fstream>
using namespace std;

static string lc(string s) {
    for (auto& c : s) c = (char)tolower((unsigned char)c);
    return s;
}

static unordered_map<string,float>
term_freq(const vector<string>& tokens) {
    unordered_map<string,float> tf;
    for (auto& t : tokens) tf[lc(t)]++;
    return tf;
}

void build_index(Index& idx, const vector<Chunk>& chunks) {
    idx.N = (int)chunks.size();
    idx.doc_lengths.resize(idx.N);
    long total = 0;
    for (int i = 0; i < idx.N; i++) {
        auto toks = tokenize(chunks[i].text);
        int dl = (int)toks.size();
        idx.doc_lengths[i] = dl;
        total += dl;
        for (auto& [term, f] : term_freq(toks))
            idx.postings[term].emplace_back(i, f);
    }
    idx.avg_dl = (float)total / idx.N;
}

vector<pair<int,float>>
query_bm25(const Index& idx, const string& q, int k) {
    const float k1=1.5f, b=0.75f, delta=1.0f;
    unordered_map<int,float> scores;
    for (auto& qt : tokenize(q)) {
        auto it = idx.postings.find(lc(qt));
        if (it == idx.postings.end()) continue;
        int df = (int)it->second.size();
        float idf = log((idx.N-df+0.5f)/(df+0.5f)+1.0f);
        for (auto& [cid, tf] : it->second) {
            float dl = (float)idx.doc_lengths[cid];
            float num = tf * (k1+1.0f);
            float den = tf + k1*(1.0f - b + b*(dl/idx.avg_dl));
            scores[cid] += idf * (num/den + delta);
        }
    }
    vector<pair<int,float>> res(scores.begin(), scores.end());
    int top = min(k, (int)res.size());
    partial_sort(res.begin(), res.begin()+top, res.end(),
        [](auto& a, auto& b){ return a.second > b.second; });
    res.resize(top);
    return res;
}

void save_index(const Index& idx, const string& path) {
    ofstream f(path, ios::binary);
    f.write((char*)&idx.N, 4);
    f.write((char*)&idx.avg_dl, 4);
    int ndl = (int)idx.doc_lengths.size();
    f.write((char*)&ndl, 4);
    f.write((char*)idx.doc_lengths.data(), ndl*4);
    int nt = (int)idx.postings.size();
    f.write((char*)&nt, 4);
    for (auto& [term, posts] : idx.postings) {
        int tl = (int)term.size();
        f.write((char*)&tl, 4);
        f.write(term.data(), tl);
        int np = (int)posts.size();
        f.write((char*)&np, 4);
        f.write((char*)posts.data(), np*8);
    }
}
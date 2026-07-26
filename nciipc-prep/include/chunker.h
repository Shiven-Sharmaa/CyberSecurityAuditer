#pragma once
#include <string>
#include <vector>
using namespace std;
struct Chunk {
    int doc_id, chunk_idx, token_start, token_end;
     string text;
};

 vector< string> tokenize(const  string& text);
 vector<Chunk> chunk_document(int doc_id, const  string& text,
                                   int window = 512, int stride = 384);
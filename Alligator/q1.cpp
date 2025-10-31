#include <bits/stdc++.h>

using namespace std;
vector<vector<int>> cards = {{1,1,0}, {3,0,0},{6,0,1},{4,0,2},{5,2,0},{7,1,1},{2,1,2}};
vector<vector<int>> moves = {{6,0,1,2,0}};
int query = 6;

vector<int> solution(vector<vector<int>> cards, vector<vector<int>> moves, int query) {
    map<int, pair<int, int>> cardPositions;
    map<pair<int, int>, int> positionToCard;
    
    for (const auto& card : cards) {
        int cardID = card[0];
        int row = card[1];
        int col = card[2];
        cardPositions[cardID] = {row, col};
        positionToCard[{row, col}] = cardID;
    }

    for (const auto& move : moves) {
        int cardID = move[0];
        int srcRow = move[1];
        int srcCol = move[2];
        int destRow = move[3];
        int destCol = move[4];
        
        positionToCard.erase({srcRow, srcCol});
        
        vector<pair<int, int>> cardsToShift;
        for (auto& [pos, cID] : positionToCard) {
            if (pos.second == destCol && pos.first >= destRow) {
                cardsToShift.push_back({pos.first, cID});
            }
        }
        
        sort(cardsToShift.begin(), cardsToShift.end(), greater<pair<int, int>>());
        
        for (const auto& [oldRow, cID] : cardsToShift) {
            positionToCard.erase({oldRow, destCol});
            int newRow = oldRow + 1;
            positionToCard[{newRow, destCol}] = cID;
            cardPositions[cID] = {newRow, destCol};
        }
        
        positionToCard[{destRow, destCol}] = cardID;
        cardPositions[cardID] = {destRow, destCol};
        
        if (srcCol != destCol || srcRow != destRow) {
            vector<pair<int, int>> cardsToShiftUp;
            for (auto& [pos, cID] : positionToCard) {
                if (pos.second == srcCol && pos.first > srcRow) {
                    cardsToShiftUp.push_back({pos.first, cID});
                }
            }
            
            sort(cardsToShiftUp.begin(), cardsToShiftUp.end());
            
            for (const auto& [oldRow, cID] : cardsToShiftUp) {
                positionToCard.erase({oldRow, srcCol});
                int newRow = oldRow - 1;
                positionToCard[{newRow, srcCol}] = cID;
                cardPositions[cID] = {newRow, srcCol};
            }
        }
    }
    
    auto finalPos = cardPositions[query];
    cout << finalPos.first << finalPos.second << endl;
    return {finalPos.first, finalPos.second};
}
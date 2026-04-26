#include <iostream>
#include <vector>
using namespace std;
int main() {
vector<int> v = {1, 2, 3, 4, 5};
// Add element
v.push_back(6);
// Print elements
for (int i : v) {
cout << i << " ";
}
return 0;
}
import { useState } from "react";
import VoiceSelection from "../components/VoiceSelection";
import CompanySelection from "../components/CompanySelection";
import TopicSelection from "../components/TopicSelection";

export default function Settings({ onStart }) {
    const [voice, setVoice] = useState("");
    const [company, setCompany] = useState("");
    const [topic, setTopic] = useState("");

    const topicDetails = {
        "Random": {
            title: "Merge Intervals",
            description: `Given an array of intervals where intervals[i] = [starti, endi], merge all overlapping intervals, and return an array of the non-overlapping intervals that cover all the intervals in the input.`,
            starterCode: `class Solution(object):
    def merge(self, intervals):
        """
        :type intervals: List[List[int]]
        :rtype: List[List[int]]
        """
        `
        },
        "Strings": {
            title: "Longest Substring Without Repeating Characters",
            description: `Given a string s, find the length of the longest substring without duplicate characters.`,
            starterCode: `class Solution(object):
    def lengthOfLongestSubstring(self, s):
        """
        :type s: str
        :rtype: int
        """
        `
        },
        "Binary Trees": {
            title: "Validate Binary Search Tree",
            description: `Given the root of a binary tree, determine if it is a valid binary search tree (BST).

A valid BST is defined as follows: <ul>
    <li>The left subtree of a node contains only nodes with keys strictly less than the node's key.</li>
    <li>The right subtree of a node contains only nodes with keys strictly greater than the node's key.</li>
    <li>Both the left and right subtrees must also be binary search trees.</li></ul>`,
            starterCode: `# Definition for a binary tree node.
# class TreeNode(object):
#     def __init__(self, val=0, left=None, right=None):
#         self.val = val
#         self.left = left
#         self.right = right
class Solution(object):
    def isValidBST(self, root):
        """
        :type root: Optional[TreeNode]
        :rtype: bool
        """
        `
        },
        "Dynamic Programming": {
            title: "Best Time to Buy and Sell Stock",
            description: `You are given an array prices where prices[i] is the price of a given stock on the ith day.

You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock.

Return the maximum profit you can achieve from this transaction. If you cannot achieve any profit, return 0.`,
            starterCode: `class Solution(object):
    def maxProfit(self, prices):
        """
        :type prices: List[int]
        :rtype: int
        """
        `
        },
        "Matrices": {
            title: "Valid Sudoku",
            description: `Determine if a 9 x 9 Sudoku board is valid. 

Only the filled cells need to be validated according to the following rules: <ul>
    <li>Each row must contain the digits 1-9 without repetition.</li>
    <li>Each column must contain the digits 1-9 without repetition.</li>
    <li>Each of the nine 3 x 3 sub-boxes of the grid must contain the digits 1-9 without repetition.</li> </ul>
Note: A Sudoku board (partially filled) could be valid but is not necessarily solvable. 

Only the filled cells need to be validated according to the mentioned rules.`,
            starterCode: `class Solution(object):
    def isValidSudoku(self, board):
        """
        :type board: List[List[str]]
        :rtype: bool
        """
        `
        },
        "Graphs": {
            title: "Minimum Height Trees",
            description: `A tree is an undirected graph in which any two vertices are connected by exactly one path. In other words, any connected graph without simple cycles is a tree.

Given a tree of n nodes labelled from 0 to n - 1, and an array of n - 1 edges where edges[i] = [ai, bi] indicates that there is an undirected edge between the two nodes ai and bi in the tree, you can choose any node of the tree as the root. When you select a node x as the root, the result tree has height h. Among all possible rooted trees, those with minimum height (i.e. min(h))  are called minimum height trees (MHTs).

Return a list of all MHTs' root labels. You can return the answer in any order.

The height of a rooted tree is the number of edges on the longest downward path between the root and a leaf.`,
            starterCode: `class Solution(object):
    def findMinHeightTrees(self, n, edges):
        """
        :type n: int
        :type edges: List[List[int]]
        :rtype: List[int]
        """
        `
        },
        "Two Pointer": {
            title: "Remove Duplicates from Sorted Array",
            description: `Given an integer array nums sorted in non-decreasing order, remove the duplicates in-place such that each unique element appears only once. The relative order of the elements should be kept the same.

Consider the number of unique elements in nums to be k​​​​​​​​​​​​​​. After removing duplicates, return the number of unique elements k.

The first k elements of nums should contain the unique numbers in sorted order. The remaining elements beyond index k - 1 can be ignored.`,
            starterCode: `class Solution(object):
    def removeDuplicates(self, nums):
        """
        :type nums: List[int]
        :rtype: int
        """
        `
        }
    }

    const isFormValid = /* company !== "" && */ voice !== "" && topic !== "" ;
    return (
        <div className="home-page">
            
            <div className="settings-container">
                <h1>Coding Studio</h1>

                <VoiceSelection voice={voice} setVoice={setVoice}/>
                {/* <CompanySelection company={company} setCompany={setCompany}/> */}
                <TopicSelection topic={topic} setTopic={setTopic}/>
                
                <button 
                    disabled={!isFormValid} 
                    onClick={() => onStart({ /* company,  */voice, topic, details: topicDetails[topic] })}>Start Interview</button>
            </div>
            
        </div>
    );
}
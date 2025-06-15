# [Double-Edge Cut Problem](https://nilmamano.com/blog/double-edge-cut-problem)

![Double-Edge Cut Problem](https://nilmamano.com/blog/double-edge-cut-problem/cover.png)

See also the related, but easier, [Single-Edge Cut Problem](https://nilmamano.com/blog/single-edge-cut-problem).

## The double-edge cut problem

You are given an undirected, unweighted graph `G` with `V` nodes and `E` edges, where each node is identified by an integer from `0` to `V - 1`.
You are also given a pair of distinct nodes, `s` and `t`, in the same connected component of `G`.

We say a pair of edges `(e1, e2)` is *essential* if removing `e1` and `e2` from `G` disconnects `s` and `t`.

Implement a data structure that takes `G`, `s`, and `t` at construction time, and then can answer queries of the form *"Is a given pair of edges essential?"*

In this post, we'll see how to construct such a data structure in linear time and space (`O(V + E)`) and answer queries in constant time.

![Example](https://nilmamano.com/blog/double-edge-cut-problem/example.png)

In this graph, if `s` is `0` and `t` is `6`, the essential pairs are `((0, 1), (0, 3))`, `((2, 4), (3, 8))`, and `((2, 4), (7, 8))`.

Any other pair of edges can be removed and `s` and `t` will remain in the same connected component, even if the graph itself is disconnected. For instance, if we remove `(4, 5)` and `(5, 6)`, node `5` ends in its own connected component, but `s` and `t` are still connected.

### Brute force solution

The brute force solution is to do nothing at construction time. For each query, take each pair of edges, remove them, and then use a graph traversal to see if `s` and `t` are still connected. This takes `O(E)` time per query.

The brute force implementation is on [github](https://github.com/nmamano/two-edge-removal-problem/blob/main/src/double_edge_cut_naive.ts). We'll compare it against the optimized solution in the [benchmark](#benchmark) at the end.

This is the key problem behind whether a *double-wall* move is valid or not in the [Wall Game](https://nilmamano.com/blog/wall-game-intro). The board of the Wall Game may look something like the picture on the left:

![Graph modeling](https://nilmamano.com/blog/double-edge-cut-problem/graph_modeling.png)

During their turn, players can build up to two walls anywhere, which is like removing two edges. The only constraint is that they cannot fully block the opponent's path to their goal (or their own). In this setting, each player forms an `s-t` pair with their goal, and the essential edge pairs correspond to **invalid** double-wall moves.

In the picture, the red player and goal are labeled `s` and `t`, and one essential pair is shown in red. There are many more essential pairs.

Imagine that you want to implement an engine for the Wall Game. One question you'll probably have to answer frequently is, *"Given a position, is a given move valid?"* The hardest type of move to check is a double wall move (the single-wall move case is handled by the [single-edge cut problem](https://nilmamano.com/blog/single-edge-cut-problem)). To answer this question efficiently, we can solve the double-edge cut problem and build one data structure for each player; we can query them to check if a double wall move disconnects any player from their goal.

### Backstory

I got [nerd-sniped](https://xkcd.com/356/) by this problem in 2021, when I was coding an engine for the Wall Game (it's on [github](https://github.com/nmamano/wallwars/blob/master/AI/include/negamax.h); it's in C++ but you can play against it on [wallwars.net](https://wallwars.net) thanks to WebAssembly). The engine is based on negamax with alpha-beta pruning, and the bottleneck is generating all the valid double-wall moves from a position.

The move generation [implementation](https://github.com/nmamano/wallwars/blob/d062b58ebfd39a3d6b9d1a996cf92c3f7dfdb1dc/AI/include/negamax.h#L262) from back then already uses some of the ideas we'll see in this post, like the fact that we can precompute two node-disjoint paths for each biconnected component, and two walls can only be an invalid if they are in the same biconnected component and there is one wall in each path (this will make sense later).

However, I couldn't figure out how to handle the case of two walls in the same biconnected component and in the two precomputed paths in constant time, defaulting to a full graph traversal for that case ([here](https://github.com/nmamano/wallwars/blob/d062b58ebfd39a3d6b9d1a996cf92c3f7dfdb1dc/AI/include/negamax.h#L598)).

I revisited the problem in 2025 because I'm [rebuilding](https://nilmamano.com/blog/wall-game-intro) the game. The key new insight is the construction of the *path-segment graph*, which we'll get to [below](#the-path-segment-graph). Something that was very helpful in this breakthrough was [vibe coding](https://nilmamano.com/blog/what-vibe-coding-actually-looks-like.mdx) a [tool](https://github.com/nmamano/two-edge-removal-problem/tree/main/python_visualization) to visualize the various graph transformations (we'll see screenshots of it in this post).

Yes, I could have coded the visualization tool myself back then, but vibe coding removed the friction. Ironically, vibe coding has a rep for only being good at starting projects and then abandoning them, but here it helped me pick up an abandoned project and finish it.

## Preliminary definitions

The algorithm relies heavily on the concepts of articulation points and biconnected components, so we'll need the following definitions:

- A [biconnected](https://en.wikipedia.org/wiki/Biconnected_graph) graph is a graph that remains connected even if any single node is removed.
- An *articulation point* is a node whose removal increases the number of connected components. A graph is biconnected if and only if it has no articulation points.
- A *biconnected component* is a maximal biconnected subgraph.
- A *bridge* is an edge whose removal increases the number of connected components.

In a connected graph with at least two nodes, every node is in at least one biconnected component. The graph can be decomposed into what is called the [block-cut tree](https://en.wikipedia.org/wiki/Biconnected_component) of the graph, which has one node per biconnected component and biconnected components are connected by articulation points. For example:

![Biconnected graph](https://nilmamano.com/blog/double-edge-cut-problem/block_cut_tree.png)

This graph on the left has four articulation points: `2`, `4`, `6`, and `7`. It has six biconnected components (shown in different colors). The bridges are `(7, 9)`, `(7, 8)`, and `(6, 12)`.

The block-cut tree is a tree in the sense that there cannot be a cycle of biconnected components--the cycle would collapse into a single biconnected component.

Here are some additional well known properties:

1. An articulation point is always in more than one biconnected component. For instance, node `7` in the picture above is in three biconnected components. An edge is always in a single biconnected component.
2. Not every edge between articulation points is a bridge. For instance, `(2, 4)` in the graph above is not a bridge.
3. Every node adjacent to a bridge is an articulation point with the exception of degree-1 nodes (like `9` in the picture above).
4. An edge is a bridge **if and only if** it is the only edge in a biconnected component.
5. In a biconnected component that is not a single edge, there are two **node-disjoint** paths between any two nodes. For instance, in the blue biconnected component, there are two paths from `2` to `4` that don't share any nodes: `2 -> 4` and `2 -> 10 -> 11 -> 4`.
6. Two biconnected components can only have one articulation point in common. Otherwise, the two biconnected components would collapse into a single one.
7. There cannot be a cycle that is not fully contained in a single biconnected component. Otherwise, all the biconnected components in the cycle would collapse into a single one. (That's why the block-cut tree is called a tree.)
8. If a simple path (path with no repeated nodes) leaves a biconnected component, it cannot return to it (for similar reasons).

### Reduction to biconnected graphs

In this section, we'll reduce the original problem to the case where the graph is biconnected, which we'll tackle in the next section.

Note that the graph from the Wall Game may not be biconnected. It may not even be connected--see, e.g., the isolated connected component in the top-left corner [above](#motivation). All we are guaranteed is that each player is in the same connected component as their goal.

First, we'll get an edge case out of the way: if `s` and `t` are neighbors and connected by a bridge, then an edge pair is essential if and only if it contains that bridge.

Next, consider the case where `s` and `t` are in the same biconnected component, `C` (which is not just a bridge). Any edge pair where at least one edge is in another biconnected component is not essential. Thus, we can focus on edge pairs inside `C`. In fact, when analyzing if an edge pair in `C` is essential, we can completely ignore the rest of the graph (we can literally remove nodes and edges outside of `C`). That is because any simple path from `s` to `t` must be fully contained in `C` (Property 8).

If `s` and `t` are not already in the same biconnected component, *any* path from `s` to `t` must go through the exact same sequence of articulation points and biconnected components. Otherwise, there would be a cycle of biconnected components, which is impossible (Property 7).

Let `C1, C2, ..., Ck` be the sequence of biconnected components that *any* `s-t` path must go through. In fact, not only is the sequence of biconnected components fixed, but also the entry and exit nodes of each biconnected component. The entry and exit nodes must be an articulation point, except for `C1`, where the entry node is `s`, and `Ck`, where the exit node is `t`. This is because there cannot be two articulation points from `Ci` to `Ci+1` (Property 6).

Among the biconnected components between `s` and `t`, there may be one or more consisting of a single edge (i.e., a bridge). Removing that bridge disconnects `s` and `t` by itself, so *any* edge pair containing it is automatically essential.

Aside from the specific case of bridge-only biconnected components, there is no way to disconnect `s` and `t` by removing two edges from different biconnected components.

What that means is that we can tackle each biconnected component `C1, C2, ..., Ck` independently, and then combine the results.

We can start by finding the biconnected components of the graph and *any* `s-t` path. From there, we can decompose the input graph into `C1, C2, ..., Ck`, and solve the problem for each of them. Instead of `s` and `t`, for each biconnected component, we use the path's entry and exit nodes as the new `s` and `t`.

This all can be done in [linear time](https://en.wikipedia.org/wiki/Biconnected_component#Algorithms), and allows us to reduce the general case to a number of instances of the biconnected case, all of which combined have an equal or smaller size than the original graph.

Next, we'll focus exclusively on the special case where the input graph is biconnected.

## Biconnected graphs

In this section, we assume that `G` is biconnected.

One obstacle we'll need to overcome is that we cannot possibly store every essential pair in our data structure given the time and space constraints. The worst case for the number of essential pairs in a biconnected graph is about `(V^2)/4`, which happens when the graph forms a single cycle, and `s` and `t` are as far apart as possible in the cycle, with `(V - 2)/2` edges between them on each side. In this case, each edge on one side of the cycle forms an essential pair with each edge on the other side of the cycle, for a total of `((V - 2)/2)^2` pairs. Since we want a data structure that takes `O(V+E)` space, we'll need to store *some information* that uses less space than the essential pairs themselves, but still allows us to answer queries in constant time.

### Finding two node-disjoint paths

In the algorithm, we'll need to find two node-disjoint paths between `s` and `t`, which we know exist because the graph is biconnected.

The naive approach of finding a simple path, removing the nodes, and then looking for a second path doesn't work, like in this case:

![Counterexample to naive approach](https://nilmamano.com/blog/double-edge-cut-problem/counterexample_two_paths.png)

For example, in this graph, there are two node-disjoint paths from `3` to `2`: `3 -> 1 -> 0 -> 2` and `3 -> 4 -> 5 -> 2`. However, if we start by finding the path `3 -> 4 -> 0 -> 2` and remove nodes `4` and `0`, we won't be able to find a second path.

Instead, we can use the following approach:

**1.** Take the undirected graph and convert it into a directed graph with the following transformation:

- Each node `u` becomes a pair of nodes, `u_in` and `u_out`, connected by an edge `u_in -> u_out`.
- Each undirected edge `(u, v)` becomes two directed edges, `u_out -> v_in` and `v_out -> u_in`. Note that the "out" nodes are always connected to "in" nodes. The only way to get to `u_out` is to come from `u_in`.

**2.** Next, we need to find two **edge-disjoint** paths from `s_out` to `t_in` in this directed graph. These two paths can be mapped to two **node-disjoint** paths in the original graph because, for each node `u` in the original graph, they can't both go through the edge `u_in -> u_out` in the directed graph.

This image shows a biconnected graph with two node-disjoint paths from `0` to `5`:

![Edge-disjoint paths](https://nilmamano.com/blog/double-edge-cut-problem/digraph_reduction.png)

Finding two edge-disjoint paths in a directed graph can be done with two iterations of the [Ford-Fulkerson](https://en.wikipedia.org/wiki/Ford%E2%80%93Fulkerson_algorithm) algorithm. Essentially, we can think of the directed graph as a flow network, where each edge has a capacity of `1`. We then need to be able to send two units of flow from `s` to `t`. The paths of the flow form two edge-disjoint paths in the directed graph.

Building the directed graph takes linear time, and each iteration of Ford-Fulkerson algorithm requires a linear-time graph traversal. Thus, this all takes linear time (see the TypeScript [implementation](https://github.com/nmamano/two-edge-removal-problem/blob/c5bbe3e9ca516c912a94dbb6074ff51fb69fa8a7/src/double_edge_cut_data_structure.ts#L608)).

### Essential edge candidates

Among all the edges in the biconnected graph, we will start by filtering down the edges that *can* be part of an essential pair to a smaller set of candidates.

We start by finding *any* two node-disjoint paths from `s` to `t`, as described above. Which we'll call the *red path* (`R`) and the *blue path* (`B`). We'll call the edges in `R` *red edges* and the edges in `B` *blue edges*.

An edge pair can only be essential if it has one red edge and one blue edge (otherwise, `s` and `t` remain connected via one of the two paths).
Thus, we can narrow down the set of candidate edges to those in `R` and `B`.

We can narrow the candidate edges further. Consider a red edge, `e1`. We know that if `e1` is part of an essential pair, `(e1, e2)`, then `e2` must be a blue edge. So, if `s` and `t` remain connected even after removing `e1` and *all* the blue edges, then we can safely say that `e1` can never be part of an essential pair. That is, `e1` is not a candidate.

We can find all the red candidates, which we'll call `RC = (r1, r2, ..., rk)`, in linear time, as follows:

- Remove all the blue edges from `G`.
- Find all the bridges in the remaining graph.
- `RC` is the list of red bridges.

![essential candidates](https://nilmamano.com/blog/double-edge-cut-problem/candidates.png)

Similarly, we can find all the blue candidates, which we'll call `BC = (b1, b2, ..., bk')`, by removing all the red edges from `G` and finding the bridges in the remaining graph that overlap with `B`:

An edge pair can only be essential if it contains an edge from `RC` and an
edge from `BC`.

However, not every edge pair with one edge in `RC` and one edge in `RB` is essential. For example:

![Non-essential](https://nilmamano.com/blog/double-edge-cut-problem/example_candidates.png)

In this graph, the essential pairs are `(r1, b1)`, `(r2, b2)`, and `(r3, b2)`. Other pairs of candidates, like `(r1, b2)`, are not essential. Intuitively, a pair of candidates is *not* essential when we can stich together parts of the red and blue paths together that avoid the candidates.

Things will get a bit complicated from now on, so it's worth mentioning that,
if we wanted to settle for not-always-constant-time queries, we could simply
store the sets of red and blue candidates, and only do an `s-t` reachability
check when we get a query with one red candidate and one blue candidate. For
every other edge pair, we can simply return `False` in `O(1)` time.

### The path-segment graph

We'll assume that `RC` and `BC` are both non-empty from now on (otherwise, we can just return `False` for every query).

To achieve worst-case constant-time queries, we'll need to construct what I call the *path-segment graph*:

This is an undirected graph that has one node for each disconnected segment of the red path after removing the red candidates, and one node for each disconnected segment of the blue path after removing the blue candidates.

In the path-segment graph, we call the nodes for the red segments `rs_0, rs_1, ..., rs_k` and the nodes for the blue segments `bs_0, bs_1, ..., bs_k'`. We'll also call them *red-segment nodes* and *blue-segment nodes*, respectively.

The nodes `rs_0` and `rs_1` are connected by an edge, which we call `r1`, just like in the original graph. Similarly, `rs_1` and `rs_2` are connected by `r2`, and so on, up to `rs_k-1` and `rs_k`, which are connected by `rk`. The same applies to the blue-segment nodes, so every edge in `RC` and `BC` is "present" in the path-segment graph.

Besides the `RC` and `BC` edges, which connect the nodes of the red-segment nodes and blue-segment nodes in two separate paths, there are also *cross edges* between red-segment and blue-segment nodes. Intuitively, these edges denote that we can go from one segment of the red path to a segment of the blue path without crossing any of the candidate edges.

Here is the path-segment graph for the example above:

![Path segment graph](https://nilmamano.com/blog/double-edge-cut-problem/path_segment_graph.png)

The red path is broken into four segments: `rs_0` is just `s`, `rs_1` is just the node between `r1` and `r2`, `rs_2` is the segment up to `r3`, and `rs_3` is the final edge of the red path. Similarly, the blue path is broken into three segments.

In the path-segment graph, there is always a cross edge between `rs_0` and `bs_0` because they share the node `s`. Similarly, there is always a cross edge between `rs_k` and `bs_k'` because they share the node `t`. For this specific example, there is also a cross edge between `rs_1` and `bs_1` because we can walk from the node to the right of `s` to the segment of `B` that starts at the node below `s` without crossing any of the candidate edges.

Next, we'll describe how to compute the cross edges.

If we take the original graph and remove all the red candidates and all the blue edges (`G - RC - B`), we are left with a sequence of connected components, each of which contains one of the red-path segments, and perhaps additional connected components that don't contain any of the red-path segments.

We call `RCC_i` the connected component in `G - RC - B` that contains the red segment `rs_i`. Thus, the red path traverses `RCC_0, RCC_1, ..., RCC_k`, in this order. We also do the same for the blue path, and call the components `BCC_0, BCC_1, ..., BCC_k'`.

Here we can see the two sets of connected components for the example above (shown in different colors):

![Path segment connected components](https://nilmamano.com/blog/double-edge-cut-problem/path_segment_ccs.png)

To compute the cross edges in the path-segment graph, we first label all the nodes in the original graph according to which `RCC_i` and `BCC_j` connected components they belong to. Then, we add a cross edge between `rs_i` and `bs_j` in the path-segment graph if and only if there is a node in the original graph that is in both `RCC_i` and `BCC_j`.

Here is another example of path-segment graph:

![Example 2](https://nilmamano.com/blog/double-edge-cut-problem/example2.png)

In this graph, the essential pairs are `(r1, b1)`, `(r1, b2)`, `(r4, b3)`, and `(r4, b4)`.

This example shows that there can be candidates that are not part of any essential pair (`r2` and `r3` in this case).

You can create the visualizations above for any grid graph with a
visualization tool I vibe coded:
https://github.com/nmamano/two-edge-removal-problem/tree/main/python\_visualization

The path-segment graph can be computed in linear time. In particular, it has at most `V` cross edges, since each cross edge `(rs_i, bs_j)` requires a node in the original graph contained in both `RCC_i` and `BCC_j`.

### Reducing connectivity in the original graph to connectivity in the path-segment graph

Starting from this section, we need one more bit of notation: we use the subindex `>=i` to indicate "all subindices greater than or equal to `i`" and the subindex `<i` to indicate "all subindices less than `i`".

The following lemma shows that instead of checking if a candidate pair, `(ri, bj)`, disconnects `s` and `t` in the original graph, we can check if it disconnects `rs_0` and `rs_k` in the path-segment graph. This makes our job easier since the path-segment graph is structurally simpler than the original graph.

**Lemma 1:** A candidate pair `(ri, bj)` is essential *if and only if* it disconnects `rs_0` and `rs_k` in the path-segment graph.

In other words:

1. If removing `(ri, bj)` disconnects `rs_0` and `rs_k` in the path-segment graph, then it disconnects `s` and `t` in the original graph.
2. If removing `(ri, bj)` does not disconnect `rs_0` and `rs_k` in the path-segment graph, then it does not disconnect `s` and `t` in the original graph.

Starting with (2), if there is a path from `rs_0` to `rs_k` in the path-segment graph that does not use `ri` or `bj`, we can turn it into an `s-t` path in the original graph that does not use `ri` or `bj` either: we follow one of the paths, say `R`, until we have to use a cross edge in the path-segment graph, say, `(rs_x, bs_y)`. We know that `RCC_x` and `BCC_y` share at least a node, `v`, so we can find a path from one of the nodes in the path segment for `rs_x` to `v` and from `v` to one of the nodes in the path segment for `bs_y`. We can then continue following the other path, `B`, until we reach `t` or need to use another cross edge, which we can handle in the same way.

For (1), we want to show that there is no `s-t` path in the original graph without `ri` and `bj`.

By definition, without `ri`, there is no way to get to `RCC_>=i` without using blue edges.
However, using blue edges before `bj` still does not allow us to reach any nodes in `RCC_>=i` (otherwise, `rs_0` and `rs_k` would still be connected in the path-segment graph thanks to a cross edge).

*(The proof for (1) is admittedly hand-wavy, I may have to revisit it.)*

### Compressing the path-segment graph

The following lemma will allow us to do a final transformation to the path-segment graph to further simplify its structure (the exact reason will be clear later).

**Lemma 2:** The following two statements are equivalent: **(a)** A candidate pair `(ri, bj)` is essential; **(b)** for every cross edge `(rs_x, bs_y)` in the path-segment graph, `ri` and `bj` are both on the same side of that cross edge (`i <= x` and `j <= y`, or `i > x` and `j > y`).

- **(a) => (b)** direction: Assume, for the sake of contradiction, that `(ri, bj)` is essential but there is a cross edge `(rs_x, bs_y)` such that `i <= x` and `j > y`. Then, we can go from `rs_0` to `bs_0`, from `bs_0` to `bs_y`, from `bs_y` to `rs_x`, and from `rs_x` to `rs_k`. This contradicts that `(ri, bj)` is essential. The other case is symmetric.
- **(b) => (a)** direction: cross edges of the form `(s1_<i, s2_<j)` do not allow us to "skip" over `ri` and `bj`. Cross edges of the form `(s1_>=i, s2_>=j)` have two endpoints neither of which can be reached from `rs_0` in the first place.

Lemma 2 is important for the following reason:

If we have a chain of edges in the path-segment graph, `rx, ..., ry`, without any cross edges coming out of the nodes between them, then all the edges in the chain have all the same cross edges on each side. A corollary of Lemma 2 is that combining *any* of these edges with a blue candidate, `bj`, has exactly the same effect on whether `rs_0` and `rs_k` stay connected. Thus, we can *compress* the chain into a single edge, `r_x,y`, as shown in the figure:

![Compressed path segment graph](https://nilmamano.com/blog/double-edge-cut-problem/compressed_path_segments.png)

In this path-segment graph, we compressed `r1`, `r2`, and `r3` into `r_1,3`, left `r4` alone (relabeled as `r_4,4`), and compressed `r5` and `r6` into `r_5,6`. The blue candidates got compressed similarly.

The result is a new graph, which we call the *compressed* path-segment graph. It is similar to the path-segment graph, but with potentially fewer nodes and edges.

We call a pair of edges in the compressed path-segment graph, `(r_x,y, b_z,w)`, *essential* if they disconnect `r_0` and `r_k`. What that means is that *any* red candidate compressed into `r_x,y` forms an essential pair with *any* blue candidate compressed into `b_z,w`.

The compressed path-segment graph has the property that *every* node is adjacent to at least one cross edge. This is important for one reason:

In the normal path-segment graph, an edge in the top path could form an essential pair with *many* edges in the bottom path, leading to a potentially quadratic number of essential pairs. In the compressed path-segment graph, each edge in the top path can only form an essential pair with *at most* one edge in the bottom path. This is because of Lemma 2: there are cross edges between every pair of edges in the bottom path, so only one of them can match the position of the top edge relative to all the cross edges.

Finally, we reached a point where **we can store all the essential pairs in `O(V)` space.** We can only do this because each edge of the compressed path-segment graph represents potentially many candidates in the original graph.

Now, we just need to compute them in linear time.

### Computing essential pairs in the compressed path-segment graph

We can use a straightforward two-pointer algorithm, with one pointer for each path. The red pointer starts at the edge `r_1,x` and the blue pointer starts at the edge `b_1,y`. For each pointer, we keep track of which cross edges we've already passed. Then, we have a case analysis:

- If both pointers have passed the same cross edges, mark the current edge pair as essential, and advance both pointers.
- If the red pointer has passed any cross edges that the blue pointer hasn't passed, advance the blue pointer.
- If the blue pointer has passed any cross edges that the red pointer hasn't passed, advance the red pointer.

With this method, we can find and store all the essential pairs in the compressed path-segment graph in `O(V)` time.

To know if a pair of candidates `(ri, bj)` in `G` is essential, we check if the compressed edges they belong to form an essential pair in the compressed path-segment graph.

## Implementation

In this section, we'll see how all the pieces fit together by designing the full data structure as described at the beginning of the post.

The data structure is implemented in TypeScript [here](https://github.com/nmamano/two-edge-removal-problem/blob/main/src/double_edge_cut_data_structure.ts). There is also the brute-force solution, tests, the visualization tool (in Python), and a little benchmark we'll use for the next section.

**Construction:**

The only constraint on `G` is that `s` and `t` are connected and different.

Find a path P from s to t in G
Find the bridges in G
Store the set of bridges that are in P
Find the biconnected components of G
For each biconnected component crossed by P with >2 nodes:
  Find two node-disjoint paths from the entry point of P to the exit point of P
  Compute the red and blue candidates
  Compute the path-segment graph
  Compute the compressed path-segment graph
  Find all the essential pairs in the compressed path-segment graph with 2 pointers
  Store the essential pairs in the compressed path-segment graph
  For each red or blue candidate, store the following information:
    - The biconnected component
    - The color (red or blue)
    - The index of the compressed edge it belongs to

Time and space: `O(V + E)`.

**Query:**

If e1 is a bridge in P or e2 is a bridge in P:
  return true
If e1 is not a candidate or e2 is not a candidate:
  return false
return true if:
  - e1 and e2 are in the same biconnected component, and
  - e1 and e2 have different colors, and
  - their compressed edges form an essential pair
else return false

Time and space: `O(1)`.

## Benchmark

I generated 10 random `30x30` grid graphs, where each edge is present with probability `0.5`. For each graph, I picked `s` and `t` randomly, making sure that `s` and `t` were connected.

I then initialized the data structure for each graph and queried it with every edge pair in the graph. I also ran all the queries with the brute-force solution.

Here are the results:

Speedup (Naive/Optimized):
Query:        237.09x
Total:        214.88x

Average query time per edge pair:
Naive:     0.002024 ms
Optimized: 0.000009 ms

Total Queries:             15506574
Positive Queries:          763483 (4.92%)

Average number of edges per graph:      1761
Average number of edge pairs per graph: 1550657

The bigger the graph, the more queries we can do, and thus the more the preprocessing pays off. With `11x11` grid graphs, which is the standard size for the Wall Game, we do only `~15k` queries per graph, and the speedup is only about `6x`.

For both `30x30` and `11x11` grid graphs, the construction of the data structures is about 3 orders of magnitude slower than solving a single query directly with a graph traversal. This is surprising, given the optimized data structure only does a constant number of graph traversals (about `10`). My theory is that the overhead comes from allocating memory (e.g., for the various derived graphs; the keyword `new` appears ~30 times in the code) and from the use of hash sets and maps.

Optimizing the code was not the main point of this post. It can be optimized further by doing things like:

- Pre-allocating and reusing the `visited` and `stack` arrays across all the functions that need to do some kind of graph traversal.
- Not explicitly constructing the directed graph in `findTwoNodeDisjointPaths()`.
- Not explicitly constructing graphs like `G - R`, `G - B`, `G - R - BC`, and `G - B - RC`. Instead, we can pass around a set of "disallowed" edges. (The path-segment graph and the compressed path-segment graphs are already not constructed explicitly.)
- Avoiding hash sets and maps with edges as keys. Instead, edges could be mapped to contiguous integers from `0` to `E - 1` (I already avoided using sets and maps when the keys are integers starting at `0`, like node indices).
- Choosing a better language for low-level optimizations...

---

*Want to leave a comment? You can post under the [linkedin post](https://www.linkedin.com/posts/nilmamano_i-just-wrote-a-blog-post-about-a-graph-problem-activity-7331121986267439104-CVWy?utm_source=share&utm_medium=member_desktop&rcm=ACoAAC6jqIwBADV70xmTEpmkxbAnN_32mssoxA8) or the [X post](https://x.com/Nil053/status/1925363965183631671).*


# [Choosing a tech stack in 2025](https://nilmamano.com/blog/2025-stack)

![Choosing a tech stack in 2025](https://nilmamano.com/blog/2025-stack/cover.gif)

I'm rebuilding one of my side projects from scratch, the [Wall Game](https://nilmamano.com/blog/wall-game-intro). The first version is playable at [wallwars.net](https://wallwars.net).

One of the first choices for a new project is the tech stack, so this blog post will go over my choice for this project and the thought process behind it.

## Requirements

To choose a tech stack, we should start from the features we need.

In this case, the easiest way to think about the feature set is that we are building a Lichess clone ([lichess.org](https://lichess.org)), except for a different board game.

I'll list here the main features and their implications about the tech we need.

### Features

- Real-time turn-based multiplayer games.
  - **Implications:** This means using **websockets**, the main networking protocol for this use case. This also means that "serverless" backends are out of the question.
- Matchmaking: people can broadcast if they are looking for someone to play, and everyone online should be able to see it.
  - **Implications:** This requires a broadcasting mechanism. Websockets also handle this use case.
- Human-level bots running [Deep WallWars](https://github.com/t-troebst/Deep-Wallwars), an Alpha-Zero-like AI.
  - **Implications:** The AI requires a beefy CPU (for the [MCTS](https://en.wikipedia.org/wiki/Monte_Carlo_tree_search)) and GPU (for ML model inferences) per move. This means that either the server needs **access to GPUs** (which would be very expensive in a cloud provider) or, the AI needs to be self-hosted.
  - The current version of the game has a C++, [minimax-based bot](https://github.com/nmamano/wallwars/tree/master/AI) that runs on the *frontend*. This requires transpiling C++ to WASM, which hasn't worked well in every browser/device. After dealing with that, I think it's not worth it, so this time I'm only considering bots that run on the backend.
- User accounts. We want to handle a mix of non-logged-in and logged-in players seamlessly.
  - Ideally, we want to support something like Google log-in.
  - **Implications:** This means either implementing authorization from scratch (this would be my first time) or using an **auth provider**.
- Satisfying visuals and animations.
  - **Implications:** We need a **modern UI library** that supports animations without requiring being an expert (which I'm not). As much as I love Lichess, I want the game to have more dynamic visuals and animations.
- Phone and tablet support. A native phone app may come later, but for now I want the website to work well on every device.
  - **Implications:** A mature UI library that supports responsive design.
- DB for things like finding recent games, your game history, leaderboards, etc.
  - **Implications:** We don't have any need for NoSQL features. A **SQL DB** should do just fine.
- Allowing users to provide their own AIs.
  - **Implications:** We will have to provide a game client as a separate repo which people can clone to run their own AI locally and connect to the site.
  - I considered the option of letting users upload their AI code to the backend, but I don't want to deal with the server costs or security concerns.
- A blog for dev journaling--you are probably reading it.
  - **Implications:** An **SSG** (static-site generator) is a good fit for this.
- A community space to discuss the game.
  - **Implications:** I already set up a discord server for the first version of the game: [discord.gg/6XFsZHGZ](https://discord.gg/6XFsZHGZ). `:)`

The following features have no additional implications on the tech stack, as far as I can tell, meaning that any stack should be able to handle them more or less equally well:

- Single player modes: playing vs bots, puzzles, and analysis board.
- ELO system and rating-based matchmaking.
- In-game chat (this is handled by websockets).
- Spectating on-going games (this is handled by websocket broadcasting).
- Sound effects and music.
- Keyboard support.
- Model training for the AI. This will be an offline process based on PyTorch, independent of the app's tech stack.
- Puzzle generation. The puzzles will be generated and uploaded to the DB as part of an offline process.

### Non-functional requirements

- This app will be heavy on business logic, *both* in the frontend and the backend.
  - **Implication:** It would be great if the stack used the **same language for frontend and backend** to allow us to share business-logic code between them. However, LLMs have made code translation pretty trivial, so this is not a hard requirement.

Usually, apps have minimal business logic in the frontend, but for a real-time game it is not ideal. For instance:

1. We want move legality checks to be instantaneous: if the user hovers over a wall slot, we want to indicate to them if they can place it or not, and this requires bridge-detection graph algorithms. We don't want to add server lag for such things.
2. Premoves are frontend-only and require graph algorithms like bridge detection to do properly.

- Small storage needs (compared to a media-centered app). All games should be stored but they shouldn't take much space. We don't have to deal with heavy data like images or video.
  - **Implications:** We don't need some kind of **CDN**.
- Tests.
  - **Implications:** I like to keep testing infrastructure to a minimum, so I won't add **testing framework** as a requirement.
- Safe rollouts.
  - **Implications:** We need a cloud provider for the backend that supports **CI/CD** and a **dev environment**.
- Low budget. Since there is no plan to monetize the game, at least initially, we want to keep costs low.
  - **Implications:** we will try to leverage free-tier plans where possible for cloud services (DB, auth, etc.).
- LLM-friendly stack. I want to be able to do CHOP (chat-oriented programming).
  - **Implications:** This means that popular frameworks and tools are preferred. Maybe more importantly, stable frameworks are preferred. (It is a pain to work with an LLM with a knowledge cutoff date earlier than the version of a framework you are using.)
- Big and stable (i.e., boring) ecosystem. We don't want simple integrations to become an adventure.
- Minimize dependencies.

[wallwars.net](https://wallwars.net) was my first project using `npm` and I was not mindful to vet dependencies, and it's been a drag to keep them updated. For instance, I used a "React wrapper" around Material UI which was not updated when a new React version came out, and it was a pain to migrate out of it (I'm sure js devs can relate). The new philosophy will be to avoid dependencies as much as possible.

- Avoid framework and hosting provider lock in.

At some point, Heroku suddenly removed the free tier that [wallwars.net](https://wallwars.net) was on. So, the new philosophy will be to try to avoid getting locked in into specific tech or services. Here are some implications of this goal:

1. This pushes me away from `next.js` because of how it subtly and not so subtly pushes you into hosting on Vercel.
2. I'd rather avoid ORMs (Object-Relational Mappers), or, if I do use one, it should be a thin wrapper around SQL and not use features specific to that ORM.
3. Rolling out my own authentication becomes a lot more appealing, as this can be particularly hard to migrate.

- Avoid the complexity of microservices.
  - Exception: it seems like a good idea to have a separate service for computing bot moves, so the main service can stay responsive by avoiding compute-heavy tasks.
- Avoid slow languages.
  - I'd be concerned about running the game logic in a language like Python.

### Non-MVP features

All of these probably make sense at some point, but that's a problem for future me. The initial scope is just to make the web experience great.

- Mobile app.
- Mailing list (to announce things like tournaments).
- Ads.
- In-game purchases.

### Subjective preferences

After the requirements, a less important factor is the developer's (i.e., my) experience and preferences.

I favor plain old procedural programming, with strong typing. I try to keep as much logic as possible in pure functions, but I don't like when functional languages are forcefully strict about it (e.g., Haskell). I'm allergic to OOP.

I'd probably rank the languages I've used by preference like this: Go > TS > Python > JS > C++ > Java. I like languages a bit on the lower level, so the "modern C++ replacements" like Rust and Zig seem appealing if I were to use a new language.

For this project, I'm not counting "learning new things" as a goal. Otherwise, I might prioritize something like Rust for the backend.

### Trade-offs

As you can see, the goals are often contradictory. For instance:

- Django is a very stable and mature framework, which is a plus, but it is Python-based, and I want a fast language.
- Wanting a stable ecosystem would mean avoiding the mess that is the JS ecosystem, but using TypeScript for both the frontend and backend seems like the easiest way of reusing business logic code between them.
- Wanting a type-safe and fast language points to Rust, but I'm not sure how good LLM completions would be compared to, e.g., TS.
- Etc, etc.

Every tech has trade-offs, and I'm sure each dev would reach a different conclusion about the right stack based on these requirements. What would *you* use?

Before we get to my choice, I'll go over the Lichess stack and the current [wallwars.net](https://wallwars.net) stack.

## Lichess stack

Lichess is a [free](https://lichess.org/@/lichess/blog/why-lichess-will-always-be-free/YF-ZORQA) open-source online chess platform with a significant share of online chess, only second to [chess.com](https://chess.com). The Lichess case study should be very interesting to any solo builders: it was built by basically one person, [Thibault Duplessis](https://lichess.org/@/thibault/blog), and it has hosted over 6 billion games. I highly recommend the video, "[How 1 Software Engineer Outperforms 138 - Lichess Case Study](https://www.youtube.com/watch?v=7VSVfQcaxFY)" by Tom Delalande.

Luckily, Thibault has given [talks](https://www.youtube.com/watch?v=LZgyVadkgmI) and written about the Lichess stack and the thought process behind it (see his [blog](https://lichess.org/@/thibault/blog) and his Reddit [AMA](https://www.reddit.com/r/chess/comments/mpasyl/i_started_lichess_ask_me_anything/)).

Thibault's philosophy is based on simplicity and minimalism, prioritizing cleaning up tech debt over adding new features. Here's an excerpt from [We don't want all the features](https://lichess.org/@/thibault/blog/we-dont-want-all-the-features/q3nOzv4n):

> Lines of code are not valuable. They are a cost, that is not paid while writing them, but while maintaining them. Sometimes years later. And they pile up.

Here is the stack:

- Bidirectional communication: WebSocket
- Frontend:
  - Type: SPA
  - Language: TypeScript
  - Framework: Snabbdom
  - CSS framework: Sass
- Backend:
  - Type: "Monolith with satellites"
  - Language: Scala (+ other languages like Rust for special tasks)
  - Framework: Play Framework
  - Ecosystem: Java/JVM
  - Database: MongoDB
  - DB cache: Redis
- Deployment:
  - Backend host: self-hosted
  - Authentication service: Custom
  - Database host: MongoDB Atlas
- Phone app: Flutter (Android and iOS)

Comments (mostly based on Tom Delalande's video):

- Scala: Thibault chose it because it is functional, high-level, and, even though it is not popular, it can leverage the JVM ecosystem. That last point is why he chose it over other functional languages like Haskell.
- Play Framework: Thibault says the framework sped up the initial development, but now he would prefer to ditch it and use "smaller independent libraries that we can swap as needed" for things like HTTP, routing, JSON, etc.
- MongoDB: Thibault would now probably go for PostgreSQL because it's open source and cheaper.
- Snabbdom: this is a minimalistic virtual DOM library. Thibault chose it because of its simplicity compared to something like React.
- Sass: Thibault said "Sass is annoying, but that's just because CSS is annoying."

One reason why I'm not considering Lichess' stack is that I want the website to have an engaging look and feel, complete with animations and cool visual effects. Thibault said on Reddit:

> I'm a programmer, not a designer, that's why it's always been quite bland, with no images and very little colors. I made up for my lack of UI skills by focusing on UX (user experience) and I think it paid out. There's lots to improve, though...

## wallwars.net stack

The current site ([wallwars.net](https://wallwars.net)) was built in 2019. It is based on the popular web stack at the time: MERN (MongoDB, Express, React, Node.js). I actually chose the stack *first*, because my goal was to learn full-stack development, and *then* chose the Wall Game as the project to learn on.

- Containerization: None
- Language: JS, latter ported to TypeScript (frontend and backend)
- Package manager: `npm`
- Bidirectional communication: Websocket
- Frontend:
  - Type: SPA
  - Build tool: the default for `CRA` (Create React App)
  - Framework: React
  - CSS framework: None, just plain CSS
  - Component library: Material UI
  - Router: React Router
  - AI: C++17 -> LLVM -> WASM (running in the browser)
- Backend:
  - Runtime: Node.js
  - Web server: Express
  - Database: MongoDB
  - DB wrapper: Mongoose
- Deployment:
  - Backend host: Heroku
  - Authentication service: Auth0
  - Database host: MongoDB Atlas

A lot of the stack is considered fairly outdated now. You can see the replacements in the next section.

Two special callouts for things I want to change:

- MongoDB: NoSQL was a mistake for this application. Everything I need from the DB is easily expressed in SQL.
- Heroku: it rug-pulled the free tier, costing $5/month now.

## My choice: modern JS ecosystem

I decided to stick with the JS ecosystem, as it seems to be consolidating around a more stable and sane set of tools.

I'll include this section of the blog post in the system prompt (e.g., "cursor
rules") when building the game. It will provide useful context for the LLM.

As discussed in the [Requirements](#requirements) section, the main reasons are:

- (My impression that) JS frontend frameworks can more easily create slick interactive UIs than other languages because they are closer to the browser. If that's incorrect, let me know!
- Factoring out and reusing business logic across frontend and backend.
- Frontend-backend communication may work better if they are implemented in the same language. E.g.:
  - Type checking and autocomplete across API boundaries.
  - [socket.io](https://socket.io/) is a JS/TS WebSocket implementation with client and server components. The fact that the two sides are built by the same team means it will probably work better out of the box.
- It's popular, so I'm hoping I'll have an easier time integrating services like authentication, DBs, etc.
- LLM friendly-ish. The [best frontend generator](https://nilmamano.com/blog/wall-game-ui?category=wallgame#appendix) I know, v0.dev, outputs TS. (Though it will be annoying to deal with evolving APIs.)
- An alright language I'm already familiar with, TS: it's type-safe(ish), fast(ish), and has good DX(ish).
- Maybe in the future, the react frontend can become the basis for react native mobile apps.

I used the Youtube video, "[The React, Bun & Hono Tutorial 2024 - Drizzle, Kinde, Tanstack, Tailwind, TypeScript, RPC, & more](https://www.youtube.com/watch?v=jXyTIQOfTTk)" by [Sam Meech-Ward](https://x.com/Meech_Ward) as a baseline for the stack. I highly recommend this video!

I found Sam's choices and explanations reasonable and clear, so I didn't change much and didn't do much additional research beyond that. (Any bad choices will be found by the tried-and-true *FAFO method*.)

- Type: Monorepo
- Containerization: [Docker](https://www.docker.com/)
- Language: [TypeScript](https://www.typescriptlang.org/) (both frontend and backend)
- Package manager: [Bun](https://bun.sh/) (both frontend and backend)
- Bidirectional communication: [Socket.io](https://socket.io/)
- Frontend:
  - Type: SPA (single-page application with client-side rendering)
  - Build tool: [Vite](https://vite.dev/)
  - Framework: [React](https://react.dev/)
  - CSS framework: [Tailwind](https://tailwindcss.com/)
  - Component library: [Shadcn/ui](https://ui.shadcn.com/)
  - Router: [TanStack Router](https://tanstack.com/router/latest)
- Backend:
  - Type: Monolith with an external service for bot moves
  - Runtime: Bun
  - Web server: [Hono](https://hono.dev/)
  - Database: [PostgreSQL](https://www.postgresql.org/)
  - ORM: [Drizzle](https://orm.drizzle.team/)
  - Bot service: some minimalistic web server (TBD) running the bot (C++, [CUDA](https://developer.nvidia.com/cuda-toolkit) & [TensorRT](https://developer.nvidia.com/tensorrt) for inference).
- Deployment:
  - Backend host: [Fly.io](https://fly.io/) (with self-hosting for the bot service)
  - Authentication service: [Kinde](https://kinde.com/)
  - Database host: [Neon](https://neon.tech/)

Comments:

- Docker should help with things like migrating hosting providers if necessary.
- Vite is a modern alternative to CRA that covers a lot of functionality, reducing dependencies. For local development, it allows hot reloading/HMR and running TS and JSX code natively. For production, it "builds" the frontend (removing TS and JSX, tree shaking, bundling, minification). Vite also allows importing node modules directly in the frontend, which may be useful for sharing code between the frontend and backend.
- Bun acts as both a package manager and a runtime, replacing both `npm` and Node. Deno would also work.
- Instead of using an SSG like `11ty` (eleventy) for the blog, I'm thinking of just using my personal blog, but with a post filter to include only posts related to the game: [nilmamano.com/blog/category/wallgame](https://nilmamano.com/blog/category/wallgame).
- Hono seems to be recommended over Express because it is more lightweight (it is built directly on top of browser standards, without additional dependencies), at the cost of less available middleware. It has a frontend client which can import the API types, adding type checking between the frontend and backend (in both directions).
- Drizzle adds type safety to the database layer. I'm not interested in ORM abstractions/features beyond that, but Drizzle can be used as a [thin wrapper](https://orm.drizzle.team/docs/overview#why-sql-like) around SQL queries.
- Tanstack Router adds type safety over the normal React Router. It also does file-based routing (*à la* next.js) instead of code-based routing.

Costs:

- Fly.io has a usage-based plan, which means that, if nobody is playing, I don't pay anything. Details: [fly.io/pricing](https://fly.io/docs/about/pricing/).
- Kinde has a free plan with up to 10500 MAU (monthly active users). After that, it increases steeply. I decided to use an authentication provider to move faster at the start. I may regret this.
- Neon has a free plan with only 0.5GB of storage. After that, it is $19/month for 10GB. This seems borderline unacceptable, so I'm happy to hear any suggestions. Maybe Supabase?

### Request-response flow diagram

![Request-response flow diagram](https://nilmamano.com/blog/2025-stack/cover.gif)

- **React Query** (also known as Tanstack Query) is an optional dependency--we could use a raw `useEffect` hook to fetch data. But it seems like a helpful wrapper around it for handling the data fetching lifecycle of API requests (caching, authentication, loading states, errors).
- **Zod** is another optional dependency. Together with Hono's compile-time type checking, it adds *defense in depth* in ensuring frontend and backend types match. It makes it easier to add runtime validations on data received by the backend. I decided to add it because I hope it will surface tricky bugs earlier. Zod can also be used to validate data sent from the backend to the frontend, but since we have full control over backend responses, compile-time type checking is probably enough.

The steps for WebSocket messages would be similar.

### Local development with Vite Server Proxy

This setup is explained by Sam in the video linked above.

In production, Vite builds the frontend, and the same server that runs the backend also serves the frontend (e.g., `wallgame.io/` serves you the frontend and `wallgame.io/api/` allows you to call the backend). This simplifies deployment and helps remove CORS issues.

The question then is: how do we match this situation when developing locally and make it so both frontend and backend share the same port?

Locally, we don't want to use a built/bundled version of the frontend served through the backend. We want to run the frontend directly with Vite to leverage features like "hot reloading" and having useful error messages right in the browser during a crash. So, we can get the frontend running (usually on port 5173 for Vite) in parallel to the backend (usually on port 3000). But if we go to `http://localhost:5173/api/`, we won't get to the backend.

To fix that, we use [Vite Server Proxy](https://vite.dev/config/server-options#server-proxy). It is a configuration that automatically redirects calls to `http://localhost:5173/api/` to `http://localhost:3000/api/`.

So, locally, everything goes through the frontend (due to the Vite Server Proxy), while in production, everything goes through the backend. What matters is that, in both cases, the same origin serves the frontend and the backend.

*Want to leave a comment? You can post under the [linkedin post](https://www.linkedin.com/posts/nilmamano_choosing-a-tech-stack-in-2025-activity-7326338741504036864-wU7c?utm_source=share&utm_medium=member_desktop&rcm=ACoAAC6jqIwBADV70xmTEpmkxbAnN_32mssoxA8) or the [X post](https://x.com/Nil053/status/1920565799535698427).*

[![What Vibe Coding Actually Looks Like (prompts included)](https://nilmamano.com/blog/vibe-coding/cover.png)](https://nilmamano.com/blog/what-vibe-coding-actually-looks-like)

[## What Vibe Coding Actually Looks Like (prompts included)](https://nilmamano.com/blog/what-vibe-coding-actually-looks-like)

SWE

The exact prompts used to create an interactive 3D torus visualization app with vibe coding.

[Read more](https://nilmamano.com/blog/what-vibe-coding-actually-looks-like)


# [Negative Binary Search and Choir Rehearsal](https://nilmamano.com/blog/negative-binary-search)

![Negative Binary Search and Choir Rehearsal](https://nilmamano.com/blog/negative-binary-search/cover.png)

One of the points we touch on in the upcoming book, [Beyond Cracking the Coding Interview](https://www.amazon.com/dp/195570600X), is that binary search has many interesting applications besides finding an element in a sorted array. I'll share an example based on a personal story that's a bit too niche for the book, but kind of fun.

A friend sings in a choir of 40-50 people, and they told me that, in the last rehearsal, the conductor could hear one person singing the wrong part but couldn't identify who. The conductor tried to isolate where the wrong part was coming from by basically **binary searching** the choir members, but there was an issue: when the conductor narrowed down the source to a small enough group, the issue disappeared. Whoever was singing the wrong part was only getting tripped up by hearing other people singing around them, but would sing their part perfectly in isolation. Eventually, the conductor gave up.

What should the conductor have done? More precisely, what algorithm should they have used to find the culprit? First, let's formalize the problem.

## The problem

You are given `n`, the number of singers, and a number `k < n/2`. You have `n` singers, say, singer `1` to singer `n`, and you can make any subset sing a song. This gives you 1 bit of information: whether they all sang it correctly or whether someone in that group messed up. All the singers always sing the right part except one, who sings the wrong part, but **only** if at least `k` people are singing with them. How do you find who it is?

## The solution

The key is to do a kind of "negative binary search," where you make everyone sing **except the subset you want to test.** You know the culprit is in a subset when everyone else sings correctly.

Example: imagine `n` is `100` and `k` is `30`.

Iteration 1:

- The culprit is in range 1-100.
- You split the range into 1-50 and 51-100.
- You want to check if the culprit is in 1-50, so you make everyone else (51-100) sing.
- Imagine they sing **correctly**. That means the culprit is in 1-50.

Iteration 2:

- The culprit is in range 1-50.
- You split the range into 1-25 and 26-50.
- You want to check if the culprit is in 1-25, so you make everyone else (26-100) sing.
- Imagine they sing **incorrectly.** That means the culprit is in 26-50.

Iteration 3:

- The culprit is in range 26-50.
- You split the range into 26-38 and 39-50.
- You want to check if the culprit is in 26-38, so you make everyone else (1-25 and 39-100) sing.
- Imagine they sing **correctly.** That means the culprit is in 26-38.

Iteration 4:

- The culprit is in range 26-38.
- You split the range into 26-31 and 32-38.
- You want to check if the culprit is in 26-31, so you make everyone else (1-25 and 32-100) sing.
- Imagine they sing **incorrectly.** That means the culprit is in 32-38.

And so on. In this way, the conductor could have found the culprit in `O(log n)` steps.

Credit to Timothy Johnson for the "negative binary search" idea, which I had never heard before.

PS. Let me know if you had seen this technique used before. Also, if you happen to be a choir conductor, I'd love to hear if (a) the problem is relatable, and (b) the algorithm may be useful to you.


# [Single-Edge Cut Problem](https://nilmamano.com/blog/single-edge-cut-problem)

![Single-Edge Cut Problem](https://nilmamano.com/blog/single-edge-cut-problem/cover.png)

See also the related, but harder, [Double-Edge Cut Problem](https://nilmamano.com/blog/double-edge-cut-problem).

## The single-edge cut problem

You are given an undirected, unweighted, connected graph `G` with `V` nodes and `E` edges, where each node is identified by an integer from `0` to `V-1`. You are also given a list, `bonded_pairs`, of `k` pairs of nodes.

We say an edge is *essential* if removing it from `G` disconnects a bonded pair.

Return a list of the essential edges.

![Input example](https://nilmamano.com/blog/single-edge-cut-problem/input_example.png)

Given this graph and the list `bonded_pairs = [[0, 1], [1, 5], [5, 7]]`, the essential edges would be `[[0, 1], [2, 4]]`:

- removing the edge `[0, 1]` disconnects the bonded pair `[0, 1]`
- removing the edge `[2, 4]` disconnects the bonded pair `[1, 5]`
- there is no way to disconnect the bonded pair `[5, 7]`

This is the key problem behind whether a wall can be added or not in the [Wall Game](https://nilmamano.com/blog/wall-game-intro). The board of the Wall Game may look something like the picture on the left:

![Graph modeling](https://nilmamano.com/blog/single-edge-cut-problem/graph_modeling.png)

Players can build walls anywhere, which is like removing an edge. The only constraint is that they cannot fully block the opponent's path to their goal (or their own). Thus, each player and its goal form a *bonded pair*, and the essential edges are the walls that **cannot** be placed.

In the picture, the bonded pairs are `[u, v]` and `[w, x]`, and the essential edges are shown in red.

Imagine that we want to implement a feature in the Wall Game website where, when you hover over a wall slot, it is highlighted in red if the move is invalid. To do this, we need to solve the single-edge cut problem. Beyond that, it could also be useful to program an engine, which needs to consider lots of moves.

Note: the graph from the Wall Game may not be connected (see, e.g., the isolated connected component in the top-left corner)--all we are guaranteed is that each bonded pair is in the same connected component. In this blog post, we assume the graph is connected for simplicity, but it is not hard to extend the algorithm to the disconnected case. We just do an initial pass to find all the connected components, and then process each one separately.

Why do we frame the problem in terms of `k` pairs, and not just two? There are variants of the Wall Game with more than two players:

![Wall Game position](https://nilmamano.com/blog/single-edge-cut-problem/four_player_game.png)

In this 4-player variant, Player 1 needs to catch Player 2 before they themselves are caught by Player 4, Player 2 needs to catch Player 3 before they are caught by Player 1, and so on. We can think of it as having four bonded pairs.

## Brute force solution

The naive solution is to consider each edge individually.
For each edge `e` in `E`, we:

1. Remove it from `G` (we denote the resulting graph as `G - {e}`).
2. Find the connected components in `G - {e}`.
3. If two bonded nodes are in different connected components, `e` is essential.

Step (1) takes `O(1)` time, Step (2) takes `O(E)` time (it can be done with a DFS or a BFS), and Step (3) takes `O(k)` time.
The total runtime is `O(E * (E+k))`.

## Efficient solution

In this section, we'll solve the problem in `O(E * k)` time. In the [next section](#optimal-algorithm), we'll see a more complicated but optimal `O(E + k)` algorithm.

We'll build up to it with a series of definitions and intermediate steps.

1. **Definition:** In a connected graph, a [bridge](https://en.wikipedia.org/wiki/Bridge_(graph_theory)) is an edge which, if removed, disconnects the graph.

In the example [above](#the-single-edge-cut-problem), the bridges are `[0, 1]`, `[2, 4]`, and `[7, 8]`.

2. **Definition:** Given a pair of nodes in a connected graph, `s` and `t`, an ***st*-bridge** is an edge which, if removed, disconnects `s` and `t`.

In the context of our problem, an edge is *essential* if it is an ***st*-bridge** for some bonded pair `[s, t]`.

3. **Observation 1:** Every `st`-bridge is a bridge, but not necessarily the other way around.
4. **Observation 2:** Given two nodes, `s` and `t`, take *any* path between them, `P`. Every `st`-bridge must be in `P`.

Observation 2 is because if we remove any edge not in `P`, `s` and `t` will still be connected via `P`.

5. **Main result:** Let `P` be any path between `s` and `t`. An edge is an `st`-bridge if and only if it is both a bridge and in `P`.

We can now formulate an algorithm based on this property:

Find all the bridges in G
For each bonded pair [s, t]:
    Find a path P between s and t
    For each edge in P:
        If it is a bridge:
            Add it to the set of essential edges

We can find all the bridges in `O(E)` time using [Tarjan's algorithm](https://en.wikipedia.org/wiki/Bridge_(graph_theory)#Tarjan's_bridge-finding_algorithm). We can find each path using DFS or BFS in `O(E)` time (interestingly, it doesn't matter how you find the path, as it can be any path). The total runtime is `O(E + k * E) = O(E * k)`.

Here's a [TypeScript implementation](https://github.com/nmamano/two-edge-removal-problem/blob/main/src/single_edge_cut_algorithm.ts).

## Optimal algorithm

If `k` is small, as in the Wall Game, the above algorithm is the most practical.
In this section, we'll see a linear-time (`O(E + k)`) algorithm, which is asymptotically optimal for any `k`.

The bottleneck of the previous algorithm is finding the `k` paths between bonded pairs. To achieve linear time, we need to do this in a single pass.

The key property we'll use is that, in [Observation 2](#efficient-solution) above, we can choose *any* path between each bonded pair. We can start by finding a *spanning tree* `T` of `G`, and focus only on the paths connecting the bonded pairs through `T`. We can find a spanning tree in `O(E)` time using a DFS or a BFS (it doesn't matter).

It will be convenient to think of `T` as a *rooted* tree, so that we can talk about node *depths* and [lowest common ancestors](https://en.wikipedia.org/wiki/Lowest_common_ancestor). We can root it at any node.

The root is at depth `0`, its children are at depth `1`, and so on. The *lowest common ancestor* of a pair of nodes `u` and `v` in `T`, denoted `LCA(u, v)`, is the node in `T` that is an ancestor of both nodes and has maximum depth.

Recall that we want to identify all the edges in `T` that form paths between pairs of bonded nodes. Between any pair of nodes `u` and `v`, there is a unique path in `T`: the path that goes from `u` up to `LCA(u, v)` and from there down to `v` (note that `LCA(u, v)` could be `u` or `v` itself).

We can start by finding the LCA of each bonded pair in `T`. We can do this in linear time using [Tarjan's off-line lowest common ancestors algorithm](https://en.wikipedia.org/wiki/Tarjan%27s_off-line_lowest_common_ancestors_algorithm).

Here is a tree for the example graph from [above](#the-single-edge-cut-problem), rooted at `7`:

![Tree example](https://nilmamano.com/blog/single-edge-cut-problem/rooted_tree.png)

Henceforth, we say that a node `u` is *bonded* if it is bonded to at least one other node.

For each bonded node `u`, we define `min_lca(u)` as follows: among the LCA's of all bonded pairs involving `u`, `min_lca(u)` is the one with **minimum** depth.

For example, imagine that, in the tree above, node `1` is involved in 3 bonded pairs: `[1, 3]`, `[1, 0]`, and `[1, 4]`. The corresponding LCA's are `2` (at depth `2`), `1` (at depth `3`), and `4` (at depth `1`). Of those, the one with minimum depth is `4`, so `min_lca(1) = 4`.

The following observation characterizes the essential edges in terms of `T`:

- **Observation 3:** A bridge of `G` is essential if and only if it is between a bonded node `u` and `min_lca(u)`.

On the one hand, if we removed a bridge between `u` and `min_lca(u)`, the bonded pair consisting of `u` and the node `v` such that `LCA(u, v) = min_lca(u)` will become disconnected. On the other hand, if a bridge is *not* between any bonded node `u` and `min_lca(u)`, every bonded pair has a path that doesn't go through it, so it is not essential.

The idea behind our linear-time algorithm is to do a traversal through `T`. At each node `u`, we want to find the LCA with minimum depth among all the bonded pairs with one node in `subtree(u)` (the subtree rooted at `u`), if any. That is, we want to find the minimum-depth node in `T` that is the `min_lca(v)` for some node `v` in `subtree(u)`. We actually only care about its depth, which we call `subtree_min_lca_depth(u)`. We can compute `subtree_min_lca_depth(u)` recursively, aggregating the results from each child as well as the depth of `min_lca(u)` itself if `u` is bonded:

Finally, we can write a simple check for whether an edge in `T` is essential:

- **Observation 4:** If `[w, u]` is an edge in `T`, where `w` is the parent of `u`, `[w, u]` is essential if and only if (1) `[w, u]` is a bridge in `G` and (2) `subtree_min_lca_depth(u) < depth(u)`.

Condition (2) says that there is some node in the subtree rooted at `u` that is bonded to a node somewhere above `u`.

Here is the full pseudocode:

Find all the bridges in G
Build a DFS tree T of G rooted at any node
Find the LCA of each bonded pair in T
Compute depth(u) for every node u in T
Compute min_lca(u) for each bonded node u
Do a post-order traversal through T as follows:
At each node u:
    visit children recursively
    if u is the root:
        return
    compute subtree_min_lca_depth(u) using the formula above
    w = parent of u
    if [w, u] is a bridge in G and subtree_min_lca_depth(u) < depth(u):
        mark [w, u] as essential

As mentioned, finding bridges takes `O(E)` time, building a spanning tree takes `O(E)` time, and finding all `k` LCA's takes `O(V + k)` time; the remaining steps, including the main tree traversal, take `O(V)` time. Considering that the graph is connected, and thus `V <= E`, the total runtime is `O(E + k)`.

*Want to leave a comment? You can post under the [X post](https://x.com/Nil053/status/1919446218398429531).*


# [The Wall Game Project](https://nilmamano.com/blog/wall-game-intro)

Welcome to the *Wall Game project*! The Wall Game is a multiplayer board game I invented, and which I'm building in public in 2025.

In this post, I'll go over [how to play](#rules-of-the-game), my approach to [building in public](#building-in-public), and the [backstory](#backstory) of the game. Once finished, it will be available at [wallgame.io](https://wallgame.io).

***"Why are you building this?"***

First of all, because I think it's a
*great* game. I've shown it to many people over the years, and the reaction is
always that (1) it's fun; and (2) it's super easy to pick up (it passes the
[subway-legibility test](http://stfj.net/DesigningForSubwayLegibility/)).

On a more personal note, my goal for 2025 is to get better at building things,
and I believe that working on things you find fun is key for consistency.

[](https://nilmamano.com/blog/wall-game-intro/livegame.mp4)

Time lapse of a 4-player game of the Wall Game.

## Rules of the game

The Wall Game is simple to understand.

**Initial setup:** In the "standard" 2-player version of the Wall Game, the board setup looks like this:

![The standard 2-player board.](https://nilmamano.com/blog/wall-game-intro/setup.png)

The standard 2-player board.

**Goal:** The red player controls the red cat and mouse, and the blue player controls the blue cat and mouse. The red player wins by having their cat catch the blue mouse before the blue cat catches the red mouse.

**How to move:** the game is turn-based. On each turn, you can make **2 actions**. Each action can be either **moving your cat**, **moving your mouse**, or **placing a wall**. Cats and mice move to adjacent cells, but walls can be placed *anywhere* between two cells on the board. The only restriction is that you cannot completely block the opponent's cat from reaching your mouse.

![The actions you can make on each turn.](https://nilmamano.com/blog/wall-game-intro/actions.png)

The actions you can make on each turn.

*That's it!* That's all the rules. It's simple enough that you can play it with just pen and paper.

To preempt the two most common questions:

- Moving diagonally counts as 2 actions.
- You cannot move through your own walls.

## Example game

Here is an example of a full game that was played on [wallwars.net](https://wallwars.net) (the first version of the site, which I'm currently rebuilding).

[](https://nilmamano.com/blog/wall-game-intro/full_game.mp4)

A game of the 'classic' variant, where there are no mice, and the goal is to get to the opposite corner first.

## Building in public

I love the concept of building in public, sharing my learnings, and getting feedback.
If nothing else, writing down my thought process helps future-me reference what I learned.

So, as I build it, I'm making a series of blog posts about the game. You can find them all at [nilmamano.com/blog/category/wallgame](https://nilmamano.com/blog/category/wallgame).

So far, I've written about:

- [Choosing a tech stack](https://nilmamano.com/blog/2025-stack)
- [Designing the UI](https://nilmamano.com/blog/wall-game-ui)
- [Designing the DB](https://nilmamano.com/blog/wall-game-db)
- The graph algorithms behind invalid move detection ([Part 1](https://nilmamano.com/blog/single-edge-cut-problem), [Part 2](https://nilmamano.com/blog/double-edge-cut-problem))

Next, I'll write about [Deep Wallwars](https://github.com/t-troebst/Deep-Wallwars), an alpha-zero-like AI made by a friend, as well as other interesting aspects of the app's implementation, like automatic puzzle generation.

Ultimately, this collection of posts should provide a playbook for building any multiplayer online game, not just the Wall Game.

## Backstory

The game dates back to my high school days, circa 2006, when my friends and I entertained ourselves with pen-and-paper games. Around that time, I played [Quoridor](https://en.wikipedia.org/wiki/Quoridor) once at a friend's house, and that inspired me to make a pen-and-paper game with similar ideas but with my own rules, like having two actions per move and unlimited walls. After some experimentation, we settled on a 10x12 board, with players starting at the top corners and having to move to their opposite corners (there was no "mouse" yet).

The game was a hit among my high-school friends, and I've basically been playing it and showing it to people ever since. For example, the name *WallWars*, which I used until the recent rebranding to the *Wall Game*, was coined by a PhD colleague in 2016 (let me know which name you like more).

In 2012, during college, I implemented a version of the game in Python (it's on [GitHub](https://github.com/nmamano/WallWarsOld)):

![The 2012 Python implementation.](https://nilmamano.com/blog/wall-game-intro/python_version.png)

The 2012 Python implementation. Back then, I called the game 'Wall-e'.

However, that version was not online, so, in 2020, I reimplemented it as a full-stack app to play with my friends during the Covid-19 lockdowns. It's currently live at [wallwars.net](https://wallwars.net). According to the DB, 421 online games have been played as of May 2025 (I'm the most active player by far).

In 2021, I started building a C++ [minimax](https://en.wikipedia.org/wiki/Minimax)-based engine for the game, which you can play against on [wallwars.net](https://wallwars.net) thanks to WebAssembly. Optimizing it was a challenge, as the branching factor is much higher than, e.g., in chess. Eventually, I got it to work well for small boards, but it was still not good enough for the exponential explosion that comes from bigger boards. That's when [Thorben](https://github.com/t-troebst) came to the rescue with the [Deep Wallwars](https://github.com/t-troebst/Deep-Wallwars) project, an alpha-zero-like engine that scales a lot better to bigger boards. This is not integrated on the site yet, but it's planned for the rebuild.

In 2023, I built a physical board to play in person:

![The physical board.](https://nilmamano.com/blog/wall-game-intro/physical_board.png)

We started experimenting with different variants, in part to accommodate 4 players, but also because we realized that exploring variants of the rule increased the game's replayability. As long as the same strategic and tactical patterns are present, variants are really fun, like playing a new level of a video game. This is also when I adopted the "cat and mouse" variant as the default.

Two of the main reasons I want to rebuild the site are to integrate Deep Wallwars and to support variants, as each of these would require a major overhaul.


# [404 - Blog Post Not Found](https://nilmamano.com/blog/dijkstra.html)

Oops! The blog post you're looking for doesn't exist or has been moved.

[Back to Blog](https://nilmamano.com/blog)





# [A topology/geometry puzzle](https://nilmamano.com/blog/merging-geometry)

![A topology/geometry puzzle](https://nilmamano.com/blog/merging-geometry/cover.png)

In this post, we'll study what kind of solids (3D shapes) we can get by taking a solid and merging two of its faces.

The goal of this project is to characterize every solid that can be created starting from a platonic solid (what that means, precisely, will be clear later). I'm ~40% of the way there.

![The five platonic solids: tetrahedron, cube, octahedron, dodecahedron, and icosahedron.](https://nilmamano.com/blog/merging-geometry/platonic-solids.png)

The five platonic solids: tetrahedron (4 faces), cube (6 faces), octahedron (8 faces), dodecahedron (12 faces), and icosahedron (20 faces), from Wikipedia.

Disclaimer: I have not done *any* literature review for this post (I did
enough of that in grad school!) so it is very likely that this space has
already been explored. This is just for fun. If you happen to know of any
related work, please let me know!

## Rules

Let's formalize what operations are valid. I'll start with (filled) 2D shapes, which are easier to visualize.

### Morphing

In topology, a cube, a sphere, and a sock are all the same thing because they can be deformed into one another without cutting or gluing. We say they are homeomorphic.

We have a similar concept here, but we also account for vertices and edges. These three 2D shapes are homeomorphic because they all have a face with 4 vertices and edges:

![Three shapes that are homeomorphic.](https://nilmamano.com/blog/merging-geometry/squares.png)

In contrast, a square is not homeomorphic with a triangle, because, even though both can be deformed into the same 'shape', the vertices and edges do not match.

The same applies to 3D solids, where two solids are homeomorphic if they can be deformed into one another without cutting or gluing, with matching faces, edges, and vertices. These two shapes are homeomorphic:

![Two solids that are homeomorphic.](https://nilmamano.com/blog/merging-geometry/cubes.png)

Two homeomorphic solids. Source for the right image: https://math.stackexchange.com/questions/74941/how-do-you-parameterize-a-sphere-so-that-there-are-6-faces

### Merging

This is the *only* operation we can do which transforms a 2D shape (or 3D solid) into another shape/solid that is not homeomorphic to the original one. I'll start with 2D.

In 2D, we can merge pairs of edges. First, it must be possible to *wiggle* the shape until the two edges line up without anything in between them. Then, we 'merge' them by lining up the edges and removing the edges and the lined up vertices. The two faces of the edges become one if they weren't already.

This should be intuitive with an image. Given a square, we can merge opposite edges or adjacent edges:

![Two edges that can be merged.](https://nilmamano.com/blog/merging-geometry/merging-edges.png)

When we merge adjacent edges of a square, we can get a vertex that connects an edge to itself. We call this shape a 'pointy circle'.

Note the requirement of "without anything in between them". This means that, for instance, we cannot merge the inner and outer edges of a 2D torus, because the torus itself is in between.

Merging two faces of a triangle results in a circle.

![Merging two faces of a triangle.](https://nilmamano.com/blog/merging-geometry/triangle.png)

There are some edge cases to address.

#### Edge Case 1: Dangling Edge

When merging two edges, we may end up with an edge that ends in the middle of a face. We call this a 'dangling edge'. By convention, we remove dangling edges as part of the merging operation, like `e` in the image below.

![A dangling edge.](https://nilmamano.com/blog/merging-geometry/dangling-edge.png)

The remaining vertex, `p`, was not adjacent to either of the merged edges, so it stays.

#### Edge Case 2: Surviving vertex

When merging two edges, the aligned vertices usually disappear. However, if a vertex is also connected to another edge which is not merged (or dangling), it will stay, like `p` in the image below. Edges `a` and `b` are not merged, so `p` stays.

![A surviving vertex.](https://nilmamano.com/blog/merging-geometry/surviving-vertex.png)

### 3D Merging

Merging in 3D is the same as in 2D, but we merge faces instead of edges.

In order for two faces to be mergeable, they must be homeomorphic (same number of vertices and edges, same holes, etc) and it must be possible to wiggle them so they line up without anything in between them.

## Tetrahedron

Characterizing the tetrahedron is trivial.

![A tetrahedron.](https://nilmamano.com/blog/merging-geometry/tetrahedron.gif)

A tetrahedron (left) and its back view (right).

I'll use gifs to show 3D solids. The gifs show the solid from the front (left) and the back (right). They were made with [this Python app](https://github.com/nmamano/mobiustorus) I [vibe coded](https://nmamano.com/blog/what-vibe-coding-actually-looks-like).

Merging any two faces of a tetrahedron gives us an 'edged sphere' (a sphere with two faces, a single circular edge, and no vertices).

![A tetrahedron with two faces merged.](https://nilmamano.com/blog/merging-geometry/edged-sphere.gif)

When I say "characterize the tetrahedron", I mean constructing a *directed acyclic graph* (DAG) of all the possible solids we can get by merging faces starting from a tetrahedron.

The tetrahedron DAG just has two nodes:

![The tetrahedron DAG.](https://nilmamano.com/blog/merging-geometry/tetrahedron-dag.png)

The tetrahedron DAG. Next to each node is the number of faces (F), edges (E), and vertices (V) of the solid.

We say a solid is *irreducible* if it cannot go through any more merging operations. Irreducible solids correspond to leaves in the DAG.

## Cube

The cube is where things get interesting. For one, the cube DAG is infinite.

![A cube.](https://nilmamano.com/blog/merging-geometry/cube.gif)

### Cube branch 1: merging opposite faces

Analogously to how merging opposite edges of a square gives us a 2D torus, merging opposite faces of a cube results in a 3D torus with a square cross-section, which we call a 'square torus'.

![A torus with a square cross-section.](https://nilmamano.com/blog/merging-geometry/square-torus.gif)

However, when we wiggle the cube, we can *twist* it before lining up the faces. This still results in a torus with a square cross-section, but one which is not homeomorphic to the non-twisted torus. In fact, the number of faces changes depending on how much we twist it.

If we twist it 90 degrees, we get a single face:

![A torus with a square cross-section.](https://nilmamano.com/blog/merging-geometry/square-torus-twist-90.gif)

If we twist it 180 degrees, we get two faces:

![A torus with a square cross-section.](https://nilmamano.com/blog/merging-geometry/square-torus-twist-180.gif)

If we twist it 270 degrees, we get a single face again:

![A torus with a square cross-section.](https://nilmamano.com/blog/merging-geometry/square-torus-twist-270.gif)

From that point on, the number of faces repeats. For instance, if we twist it 360 degrees, we get four faces again.

![A torus with a square cross-section.](https://nilmamano.com/blog/merging-geometry/square-torus-twist-360.gif)

If we keep twisting it more, the number of faces repeats `4 -> 1 -> 2 -> 1 -> 4 -> 1 -> 2 -> 1 -> ...`, but none of those solids are homeomorphic. So, by twisting, we can get an infinite number of different solids.

If we take the square torus without any twisting and merge adjacent faces, we get a torus where the cross-section is a pointy circle.

![A torus with a pointy circle cross-section.](https://nilmamano.com/blog/merging-geometry/pointy-circle-torus.gif)

If we merge opposite faces instead, we get a torus with a torus cavity, i.e., a torus with a 2D-torus cross-section.

![A torus with a hole.](https://nilmamano.com/blog/merging-geometry/hole-torus.gif)

The square toruses that have 1 or 2 faces after twisting (e.g., with a 90 degree or 180 degree twist) are irreducible because there are not enough faces.

The square toruses that have 4 faces after twisting (e.g., with a 360 degree twist) are not irreducible, regardless of how much we twisted them:

- If we merge opposite faces, we get the a torus with a hole again. Surprisingly, this merge "undoes" the twisting.
- If we merge adjacent faces instead, we get a pointy-circle torus again, but this time the edge twists around the cross-section. The amount of twisting depends on how much we twisted the cube, so we can get an infinite number of different pointy-circle toruses. Here is the pointy-circle torus with 360 degree of twisting:

![A pointy circle torus.](https://nilmamano.com/blog/merging-geometry/twisted-pointy-circle-torus.gif)

This covers every solid we can get from a cube by merging opposite faces.

### Cube branch 2: merging adjacent faces

Starting from a cube, if we merge adjacent faces, we get a cylinder with a pointy-circle cross-section.

![A cylinder with a pointy circle cross-section.](https://nilmamano.com/blog/merging-geometry/pointy-circle-cylinder.gif)

From there, we can merge the top and bottom faces of the cylinder to get a pointy-circle torus. When we do that, we can twist it to get all the same infinitely many pointy-circle toruses with twisting that we got from the square toruses.

### Cube DAG

We can now complete the cube DAG:

![The cube DAG.](https://nilmamano.com/blog/merging-geometry/cube-dag.png)

The cube DAG. We have omitted solids obtained by twisting more than 360 degrees. The actual DAG is infinite.

Personally, what I find interesting about the cube DAG is how it is possible to reach the solids that require two steps in multiple ways.

## Counting faces by cross-section sides and twists

Before getting to the other platonic solids, I'll go on a tangent to show a cute result:

A torus with a `k`-gon cross-section and `n` 'face twists' has `GCD(k, n)`
faces.

Where:

- `GCD` is the greatest common divisor
- A `k`-gon is a polygon with `k` sides
- A face twist is a twist of `360/k` degrees. For instance, 1 face twist means that, in one full rotation of the torus, each face ends up one face over.

We already saw some examples with the square torus (a 4-gon torus):

- `0` face twists (0 degrees): `GCD(4, 0) = 4` faces
- `1` face twist (90 degrees): `GCD(4, 1) = 1` face
- `2` face twists (180 degrees): `GCD(4, 2) = 2` faces
- `3` face twists (270 degrees): `GCD(4, 3) = 1` face
- `4` face twists (360 degrees): `GCD(4, 4) = 4` faces

This result also explains why the number of faces repeats as we twist the square torus further.

Here are some examples with a different `k`-gon, a 12-gon:

![A 12-gon torus with 8 face twists.](https://nilmamano.com/blog/merging-geometry/12-gon-8-twist.gif)

A 12-gon torus with 8 face twists. GCD(12, 8) = 4 faces.

![A 12-gon torus with 9 face twists.](https://nilmamano.com/blog/merging-geometry/12-gon-9-twist.gif)

A 12-gon torus with 9 face twists. GCD(12, 9) = 3 faces.

![A 12-gon torus with 10 face twists.](https://nilmamano.com/blog/merging-geometry/12-gon-10-twist.gif)

A 12-gon torus with 10 face twists. GCD(12, 10) = 2 faces.

![A 12-gon torus with 11 face twists.](https://nilmamano.com/blog/merging-geometry/12-gon-11-twist.gif)

A 12-gon torus with 11 face twists. GCD(12, 11) = 1 face.

![A 12-gon torus with 12 face twists.](https://nilmamano.com/blog/merging-geometry/12-gon-12-twist.gif)

A 12-gon torus with 12 face twists. GCD(12, 12) = 12 faces.

If you want to play with different `k`-gons and number of face twists, the source code for the Python app is [here](https://github.com/nmamano/mobiustorus).

The argument for why the number of faces is `GCD(k, n)` is as follows:

**Proof:** Pick any cross-section of the torus, `C`. `C` is a `k`-gon, so we can label its edges with `0, 1, 2, ..., k-1` along the twist direction.

If we walk along a face of the torus, starting from `C`, edge `0`, by the time we get back to `C`, we'll have moved `n` edges over in the twist direction. Since there are only `k` edges, that means we'll end up at edge `n % k`.

If we keep walking along the torus, we'll reach, edges `0`, `n % k`, `2*n % k`, `3*n % k`, and so on, until we reach a number `i*n` that is a multiple of `k` and we get back to edge `0`. All these edges belong to the same face of the torus. Thus, each face of the torus covers `i` edges of `C`, making the total number of faces `k / i`. Now we just need to see that `k / i = GCD(k, n)`.

The number `i*n` is the first multiple of `n` that is also a multiple of `k`. In other words, `i*n = LCM(k, n)`, where `LCM` is the least common multiple.

Recall the `GCD-LCM` identity: `GCD(a, b) * LCM(a, b) = a * b`.

Using that `LCM(k, n) = i*n`, we get that `GCD(k, n) * (i*n) = k * n`, so `k / i = GCD(k, n)`. ∎

## Octahedron (work in progress)

As of March 2025, I haven't finished the octahedron DAG yet.

![An octahedron.](https://nilmamano.com/blog/merging-geometry/octahedron.gif)

An octahedron.

### Octahedron branch 1: merging edge-adjacent faces

If we merge two faces sharing an edge, we get this shape with two triangle faces and two 2-gon or 'digon' faces (a closed shape with two edges) which I'll be calling 'eye' shapes:

![Result of merging adjacent faces of an octahedron.](https://nilmamano.com/blog/merging-geometry/dorito.png)

*Can anyone suggest a good name for this shape? I'll go with 'Dorito' for now.*

![Result of merging adjacent faces of an octahedron.](https://nilmamano.com/blog/merging-geometry/dorito.gif)

If we merge the two 'eye' faces of the 'dorito', we get a kind of torus with a single point in the center instead of a hole, and an edge along the outside of the torus. Since the two eyes share a vertex, no twisting is possible.

![Result of merging the two eyes of a dorito.](https://nilmamano.com/blog/merging-geometry/dorito-eyes-merged.png)

Unfortunately, as I mentioned, I vibe coded the Python app to draw the 3D solids, and this is the limit of what I've managed to get Claude to draw. So, for the remaining faces I only have sketches or nothing at all.

If we merge the two triangle faces, it's hard to visualize what happens, but (*I think*) one of the eyes becomes an inner face and the other an outer face. The 'dorito' shape has a vertex shared by all four faces, so, since it is adjacent to the two 'eyes', which are not merged, it stays after the merge (see edge case 2 in [merging](#merging)). That means that the outer and inner face share a vertex.

The final shape looks like a 3D 'teardrop' solid with a 'teardrop' cavity, where both teardrops share the top vertex.

![Result of merging the two triangles of a dorito.](https://nilmamano.com/blog/merging-geometry/dorito-triangles-merged.png)

Teardrop solid with a teardrop cavity. Source for the left image: https://www.thingiverse.com/thing:528974

*~Insert joke here about how the eyes turned into teardrops.~*

That's all we can do in the first branch of the octahedron DAG.

### Octahedron branch 2: merging vertex-adjacent faces

If we merge two faces sharing a vertex, we get this shape, which I'll call the 'petal'.

![Result of merging two faces of an octahedron sharing a vertex.](https://nilmamano.com/blog/merging-geometry/petal.png)

The only thing we can do with the petal is merging the two pointy-circle faces sharing a vertex, which results in a torus with a single vertex in the center instead of a hole.

![Result of merging the two pointy-circle faces of a petal.](https://nilmamano.com/blog/merging-geometry/petal-picks-merged.png)

That ends this branch.

## Octahedron branch 3: merging opposite faces

This is the most interesting branch. Anytime we merge two faces that don't share any edges or vertices, we form some kind of torus. In this case, I *think* it's a torus with a hexagonal cross-section, except for a single point in which three of the edges 'collapse' into vertices and the cross-section is a triangle (at least, that's one way to draw it -- it's not the only way). Here is my best attempt at sketching the 'collapse point':

![Sketch of merging opposite faces of an octahedron.](https://nilmamano.com/blog/merging-geometry/hexagonal-torus-sketch.png)

Sketch of merging opposite faces of an octahedron. The red hexagons are not actual edges, they are just to help visualize the hexagonal cross-section. It would be a lot more sensible to draw this in Blender...

If I counted correctly, this solid has 3 faces, 6 edges, and 3 vertices regardless of how much twisting we do. I'm not sure whether it is irreducible, and whether that depends on the amount of twisting.

### Octahedron DAG

This is what I have so far:

![The octahedron DAG.](https://nilmamano.com/blog/merging-geometry/octahedron-dag.png)

Incomplete octahedron DAG. Naming all these solids became too much :)

Unlike the cube, we don't get any shared solids between the branches.

## What's next?

I don't know much about the dodecahedron and icosahedron yet. What's clear is that I pushed the limit of both vibe coding and of the 2D drawing editor (the amazing [Ipe](https://github.com/otfried/ipe)). I think Blender is the right tool for this, and I'm actually [curious enough](https://x.com/Nil053/status/1902868359777329373) about what these shapes look like that I started messing around with it. So far, I managed to make this (scuffed) two-faced solid, which I incorrectly thought could be obtained from the octahedron:

![A two-faced shape.](https://nilmamano.com/blog/merging-geometry/blender-experiment.gif)

This project started from [seeing](https://x.com/PhysInHistory/status/1892892736048468367) this gif:

The concept of a *solid* mobius strip was new to me, and I started thinking about variations and how to construct them. That led me to the idea of starting with a cube and merging two faces. Then, I did something very common in math: I started thinking about possible generalizations.

[![Problem Solving BCtCI Style](https://nilmamano.com/blog/problem-solving-bctci-style/cover.png)](https://nilmamano.com/blog/problem-solving-bctci-style)

[## Problem Solving BCtCI Style](https://nilmamano.com/blog/problem-solving-bctci-style)

A problem walkthrough using the concepts from Beyond Cracking the Coding Interview.

[Read more](https://nilmamano.com/blog/problem-solving-bctci-style)



# [My family during the Spanish Civil War](https://nilmamano.com/blog/spanish-civil-war)

All four of my grandparents were in Catalonia during the 1936-1939 Spanish Civil War. Coming from families from both sides, each had a different journey through it. Bits of "family lore" about the war times have trickled down to me through the years, but I decided it's worth trying to put together and contrast their stories.

Eventually, I'd like to expand this to my four grandparents, but for now, I'll focus on one of my grandad's story, which I'll call J.M.

## J.M.

**Disclaimer:** Since J.M. already passed away, this account is based on how
he chose to talk about it (and what to include), and on the imperfect memory
of his children. As such, it may not be historically accurate.

Born in 1920 and raised in Barcelona, J.M. was 16 when the military *coup d'état* that started the war happened. Barcelona was one of the 'strongholds' of the republican side, but he actually came from a family that supported the military takeover led by the soon-to-be fascist dictator, Franco.

The younger of two brothers, he was not the 'family heir', so he was treated accordingly. When the mandatory draft happened, his dad hid himself and the older son above a fake ceiling, but J.M. was not spared in the same way.

And thus, in 1938, at 18, he became a member of what was known as the ["Baby bottle levy"](https://en.wikipedia.org/wiki/Leva_del_biber%C3%B3n), a levy of boys aged 14-18 drafted to fight for the republican side when things got dire.

His first and last major operation was the [Battle of the Ebro](https://en.wikipedia.org/wiki/Battle_of_the_Ebro), not far from home for J.M., about 100 miles south of Barcelona. It was one of the final major counterattacks by the republican side. It was also one of the bloodiest.

For historical context, this battle started just months before Germany, the UK, France, and Italy signed the Munich agreement, which pretty much sealed the spanish republic's fate. At the time, the Republican side was losing ground rapidly, but tension in Europe was getting to a boiling point, and the republican side was hoping that an Europe-wide conflict would erupt and Spain would get sucked into it, at which point they would have support from other european powers (especially their neighbor, France). So, all they needed was to last long enough. It was a wager that turned out to be correct, but it came too late. France and the UK's attempt to appease Nazi Germany with the Munich agreement crushed that hope, and the spanish war was officially over a few months before WW2 began.

Anyway, so my grandad makes it to the battle of the Ebro, and the army discovers in him a valuable talent that spares him the frontline. At the time, the republican side had just received a large batch of Czechoslovakian rifles, but--largely due to the language barrier--they had trouble operating them. J.M. had a talent for technical drawing, and made drawings showing the steps to assemble and disassemble the rifles.

When I asked about this story, my aunt named Czechoslovakia specifically as
the source of the rifles, which checks out with Wikipedia.

For the next part of the story, there are two pretty different accounts. What we know for sure is that the republican side was under heavy bombing, and J.M.'s *company* (not sure what's the technical term) was hiding in a bunker, and the bunker was hit directly and critically, killing everyone or almost everyone inside.

In one account, J.M. and a friend of his were the only ones outside the bunker, because it was claustrophobically crowded. Each of them was sitting under a different tree. When the bunker got bombed, his friend died too, either by the same or a different bomb, making him the only survivor. In the other account, he was also inside the bunker, but behind a blind corner that was spared the blast.

The next thing we know about J.M. is that he deserted during the battle of the Ebro, and he started making his way toward the French border, about 200 miles north. Initially, his only clothes were his military uniform, an obvious tell of a deserter, which makes it extremely dangerous to be wandering around alone. As the story goes, he got hold of a herd of sheep, and walked north with it. He used the herd as a cover: he said he was walking alone because he was in charge of bringing the sheep to feed the big mass of refugees also headed north. Eventually, farmers along the way helped feed him and gave him new clothes.

Apparently, he was stopped at least once by military, possibly multiple times and from both sides, and asked "what side do you belong to?" to which he answered something along the lines of, "I don't belong to any side, shoot me if you want" and continued on his way.

Eventually, he made it to the *Argelers* refugee camp in southern France. A camp which, like the other French camps for spanish refugees, would later be relabeled as concentration camps due to the dire conditions. The cold and famine was bad enough that when the war ended, one night, J.M. escaped and headed back to Spain.

Apparently, he didn't receive any punishment for fighting for the republican side. He simply had to spend the next three years doing mandatory military service, this time for the nationalist side--the opposite side he fought for.

All in all, in his words, he "wasted seven years on the whole ordeal." He never claimed to support either side, and always showed skepticism toward any kind of political and religious movements and ideologies.

When he was finally able to move past all that, he pursued his passion for art. He worked in graphic design and used that money to pay for an arts degree in college, where he met my grandmother, with whom he shared a love for painting.





# [What Vibe Coding Actually Looks Like (prompts included)](https://nilmamano.com/blog/what-vibe-coding-actually-looks-like)

![What Vibe Coding Actually Looks Like (prompts included)](https://nilmamano.com/blog/vibe-coding/cover.png)

One afternoon, I was lying in bed with a case of *malaise*. I was thinking about this gif I had seen on [X](https://x.com/PhysInHistory/status/1892892736048468367) earlier and how it would be cool to have an interactive visualization for shapes like this:

I wasn't in the mood to start coding a 3D graphics app, but vibe coding is fun, and chill, and lazy, so I thought, "I'm not doing it, but I'll ask Claude and see what happens."

The term *vibe coding* went viral from an Andrej Karpathy [tweet](https://x.com/karpathy/status/1886192184808149383). However, a lot of people still don't know what it is or how it works.

Vibe coding is when you code a project by repeatedly prompting an LLM to add features and make changes, without looking at the code. The LLM proposes a code change, and rather than reviewing it, you click "accept" and check if it does what you want. If it doesn't, you prompt it to fix it or undo the change and refine your prompt.

For me, it has made side projects a lot more fun and productive (the entire website you are reading this post on was vibe coded), so I want to share how it works and **make it concrete** by showing the exact prompts used to create a project.

### The project

I'll show the first **17** prompts I used for [github.com/nmamano/mobiustorus](https://github.com/nmamano/mobiustorus), an interactive python app for visualizing 3D toruses with different polygonal cross sections and 'twists'.

This was the final result after the 17 prompts, including failed ones:

![Final result: an interactive 3D torus visualization with polygonal cross sections and twists](https://nilmamano.com/blog/vibe-coding/state17.gif)

### Setup

I used Claude-3.5-Sonnet via the Cursor IDE. The two popular choices for vibe coding right now seem to be Cursor and Windsurf. I've only tried Cursor so I don't have an opinion on which is better.

I wasn't trying to be fast or efficient, but I clocked the whole thing at 35 minutes, so about 2 minutes per prompt. The LLM is fast, so the main bottleneck was writing the prompts.

To be fair, this was probably a lucky/*happy* run, and it could have taken longer. However, LLMs keep getting better (we now have *thinking mode* for Claude 3.7 in Cursor), so the trend will be the opposite.

The [resulting code](https://github.com/nmamano/mobiustorus/blob/9bb4a44872dff9d740e03a46d05c9017d2fbe5f1/mobius.py) was 180 LoC.

## The prompts

> 1. write a python script that draws a 3d torus. make it interactive if possible

![An interactive 3D torus visualization with color gradient](https://nilmamano.com/blog/vibe-coding/state1.gif)

Result from prompt 1.

Notice how I don't start by asking for the final state. Part of vibe coding is *chuncking* what you want to do into a series of conceivable steps.

> 2. can you make the torus more like a doughnut? make the cross section a circle

The AI pushed back saying it was already a circle.

> 3. the problem is in the visualization then. the axises don't all have the same scaling

![Torus with corrected scaling on all axes](https://nilmamano.com/blog/vibe-coding/state3.png)

Result from prompt 3.

It's good to fix issues (like the distorted scaling) before trying to add more features.

> 4. can you hide the axes and planes so there's only the torus left

![Torus with hidden axes and planes](https://nilmamano.com/blog/vibe-coding/state4.png)

Result from prompt 4.

> 5. now the challenging part. Add a parameter k, which you can initialize to 4 by default. Then, instead of a circle, the cross section should be a regular polygon with k sides. like a square for k = 4

![First attempt at a polygonal torus that looks like a lamp](https://nilmamano.com/blog/vibe-coding/state5.png)

Result from prompt 5.

> 6. it didn't work. it looks more like a lamp

![Polygonal torus with gaps between faces](https://nilmamano.com/blog/vibe-coding/state6.gif)

Result from prompt 6.

> 7. that's almost correct, but thre's a weird gap where some of the sides don't touch

The AI made some changes that didn't fix it.

> 8. still happening (with attachment: a screenshot of the shape)

This finally fixed it.

**Tip:** I didn't do it here but it's often easier to roll back a bad change
and refine your prompt than to try to fix it.

> 9. color each face of the torus with a different color

I ran into some compilation errors.

> 10. help (with attachment: the error from the terminal)

![Interactive torus with a slider to change the number of sides](https://nilmamano.com/blog/vibe-coding/state10.gif)

Result from prompt 10.

> 11. add a way to change the k parameter in the interaction

![Torus with twisting added](https://nilmamano.com/blog/vibe-coding/state11.gif)

Result from prompt 11.

Notice how I didn't specify what the UI for changing the parameter should look like. Often, the LLM does a better job when it has fewer constraints.

> 12. can you add an option to add twisting to the shape. in one full rotation of the 'torus' each face has twisted to matchup with the 'next' face

![Torus with face alignment in twists](https://nilmamano.com/blog/vibe-coding/state12.gif)

Result from prompt 12.

> 13. It should skip twists where the faces don't perfectly match. So, depending on the number of faces, it should calculate the degrees to twist to align the next face, and that should be the smallest incremental twist

![Torus with colored twist faces aligned](https://nilmamano.com/blog/vibe-coding/state13.gif)

Result from prompt 13.

> 14. can you support one more twist, so that each face can match with its original starting face

This worked.

> 15. here's a crazy idea. instead of showing the torus once, show it twice, side by side, with the second one looking at it from the opposite side (like from deep in the z axis i guess)

It showed two toruses, but they moved independently.

> 16. Nice!! I want the position of the 2 toruses to be related though. when i move one, the other should move too, but seen from the opposite side

![Two toruses side by side showing different perspectives](https://nilmamano.com/blog/vibe-coding/state16.gif)

Result from prompt 16.

> 17. close enough. now the 2 are moving together as i wanted, but i'm not getting the 2 perspectives that i want. the left torus is perfect as is. the right torus should be as if i was looking at the left torus from behind

This produced the final result I showed at the beginning.

![Two synchronized toruses showing front and back views](https://nilmamano.com/blog/vibe-coding/state17.gif)

Result from prompt 17.

## Some thoughts

After this initial experiment, I used this app to write another blog post, [Merging Geometry](https://nmamano.com/blog/merging-geometry).

I kept adding features to this app, like:

- making the shapes rotate automatically
- a button to download gifs of the animations
- adding more shapes
- remembering which shape was open the last time the app was used and opening it directly (using local storage)
- automatically reopening the app when the code changes

It is now ~1200 LoC, and I still have no idea whatsoever how to draw a 3D shape with Python.

***"But you're not learning anything!"***

Some people think that that is a *wasted opportunity* and that it makes me a worse programmer because I am not learning anything.

Here is the thing: people operate in different modes. I wanted these visualizations to satisfy my curiousity, and later to write the blog post, not because I wanted to code. I was in *writer mode*. My goal was to convey information clearly, and vibe coding is a *tool* that helped me do that.

***"Is coding a useless skill now?"***

As much as I like vibe coding, I'll push back against this idea. Personally, I wouldn't trust vibe coding to handle anything with real users or personal data. I would still use LLM chats, but I would want to control the architecture and understand the codebase.

Even if I didn't look at the code for this project, I still needed an intuitive understanding of how hard it is to code something (for an LLM) in order to chunk the project into doable steps.









# [Lifecycle of a CS research paper: my knight's tour paper](https://nilmamano.com/blog/knights-tour)

In math research, the way we arrive at a proof is nothing like how it is laid out in a paper at the end.
The former is messy, full of false starts and dead ends.
The latter is designed to be formal, concise, and neutral, devoid of any trace of personality of the authors.

While rigor is very important in a paper with theorems and proofs, it has the unfortunate side effect of being unrelatable. A common reaction is *"How did they come up with that? I could never."*

So, as someone who'd love to increase interest in theoretical CS research, I'll take one of my papers and try to make it more relatable by talking about everything that is *not* in it.

I'll choose a paper that was particularly *fun*: [Taming the Knight's Tour: Minimizing Turns and Crossings](https://arxiv.org/pdf/1904.02824.pdf) (co-authored with Juan Jose Besa, Timothy Johnson, Martha C. Osegueda, and Parker Williams).

## Background: the knight's tour problem

A knight is a chess piece that moves in an L-shape:

![Knight moves](https://nilmamano.com/blog/knights-tour/knight_moves.png)

The traditional formulation of the [knight's tour problem](https://en.wikipedia.org/wiki/Knight%27s_tour) goes as follows:

A knight starts in any square of a chess board. The challenge is to visit every square, without repetition, using only knight moves, and return to the starting square. This puzzle becomes an interesting computational problem when generalized to `n x n` boards for any `n`.

![Example of a knight's tour from Wikipedia](https://nilmamano.com/blog/knights-tour/knights_tour_wiki.gif)

Example of a knight's tour from Wikipedia

## Inception

The [research group](https://ics.uci.edu/~theory/) where I did my PhD had a fun little tradition: every Wednesday afternoon, we'd have a "tea time", where someone would propose a math riddle, and we'd try to solve it as a group while drinking tea and eating cookies.

Our group does research on *graph drawing* (among other things), which is the study of graph embeddings in the plane. One of the central questions is about how to draw a graph in the plane with as few edge crossings as possible. With that in mind, I proposed the following problem during tea time:

*"Look at a knight's tour on an 8x8 chessboard as a graph embedding, where the squares are nodes and the knight moves are edges. Can you find the tour that minimizes the number of crossings?"*

This created a cute intersection between a classic riddle and one of the group's research interests.

The co-authors mentioned above were other PhD students from the group who came to tea time that week (except for Parker Williams, who will come into the picture later). This ended up being my only publication without any professor involved!

*"Recreational mathematics is a gateway drug to hard math."* - Erik Demaine (I
believe).

## Initial exploration

The first step is always the play around with the problem by hand to start building some intuitions around it.
We started drawing tours on the whiteboard while trying to avoid crossings as much as possible.

The first observation was that the 8x8 board felt too small and constrained to avoid crossings, so we decided that it would be more interesting as a generalized problem in `n x n` boards for arbitrarily large `n`.
This put us more firmly in CS territory, where we care about how things *scale*. Instead of finding a specific solution, we were now looking for a generic way of constructing tours for any `n x n` board with a small number of crossings. That is, we were looking for an *algorithm*.

## Upper and lower bounds

When looking at a new problem, it is always a good idea to establish

- (1) how well do existing algorithms do on the problem, and
- (2) what is the absolute best we could hope for.

The former sets a baseline for what we have to beat to have something interesting at all; it gives us an *upper bound* on the number of crossings in the optimal tour. The latter establishes a *lower bound*.

Sometimes, you find that the upper bound and the lower bound match, in which case there is no room for progress and the project is essentially dead.

When thinking about these bounds, we realized that it'd be easier, while still interesting, to minimize *turns* instead of *crossings*. A "turn" is a cell where the knight changes directions. Turns are easier to work with because a cell is either a turn or it is not, while an edge can be involved in multiple crossings. So, we decided to focus on minimizing turns.

As you can see, we have already reframed the problem twice. Trying to find the
most interesting (but still doable) questions is an organic part of research.

Working with turns instead of crossings gave us a trivial lower bound: every cell along the edge of the board **must** be a turn, so we have at least `4n - 4` turns on an `n x n` board.

![Every edge cell must be a turn](https://nilmamano.com/blog/knights-tour/edge_turns.png)

Every edge cell must be a turn

To establish an upper bound, we looked at how existing algorithms do on the metric of minimizing turns. We found that there are only two main kinds of knight's tour algorithms:

1. Backtracking algorithms with heuristics like *Warnsdorf's rule*. The idea is to construct a tour step by step, always going to the most promising next move (according to the rule), and backtrack if we get stuck. These algorithms, while very effective for 8x8 boards, quickly reveal their exponential nature for larger boards.

![Tour found by backtracking with Warnsdorf's rule](https://nilmamano.com/blog/knights-tour/warnsdorf_tour.png)

Tour found by backtracking with Warnsdorf's rule. Source: ianparberry.com/research/puzzles/knightstour/

2. Divide-and-conquer algorithms, which split the board into four quadrants, 'solve' each quadrant recursively down to, e.g., 8x8 boards, and then change some of the boundary moves to concatenate the different bits together.

![Tour found by divide-and-conquer](https://nilmamano.com/blog/knights-tour/divide_and_conquer_tour.png)

Tour found by divide-and-conquer. Source: ianparberry.com/research/puzzles/knightstour/

Backtracking algorithms are inherently uninteresting because they don't scale and don't have structure that can be analyzed.

The divide-and-conquer algorithms, however, allowed us to establish an upper bound: on an `n x n` board, the board ends up divided into about `~n^2/64` "tiles", assuming that the base case is `8x8`. Each of these tiles must have at least one turn, so the tours from these divide-and-conquer algorithms have at least `O(n^2/64) = O(n^2)` turns.

This leaves us with a very interesting gap between the `O(n^2)` upper bound and the `O(n)` lower bound.

At the time, after playing around with the problem and looking at existing
backtracking and divide-and-conquer solutions, I had a strong intuition that
`O(n^2)` was the best possible number of turns. I had an even stronger
intuition that `O(n)` turns was impossible. At best, I thought we could find
something in between, like `O(n^1.5)` turns.

## First approach: generalizing from small boards

A common problem-solving technique is to look at the solution for small inputs, and try to extrapolate the pattern to larger inputs. In our case, that means brute-forcing the problem for small boards, and see what the optimal solutions look like there. Maybe, that would show us some emergent structure that we could use to construct larger solutions.

However, even for small boards, it is far from easy to find the optimal tour. To that end, Tim encoded the problem in the [Z3 theorem solver](https://en.wikipedia.org/wiki/Z3_Theorem_Prover), a general optimization tool, to find the tour with the least number of turns.

This was a laughable failure: the solver took about 2 hours to run for `6x6` boards (the smallest size with a tour), and it never finished running for the next smallest board with a tour, the `8x8` one.

Here is the optimal tour for `6x6` boards:

Looking at the "optimal" tour for 6x6 boards gave absolutely no insight: due to the small size, almost every square was a turn. The optimal tour has a total of 32 turns in 36 squares. Face palm moment.

## Second approach: aim for the sky

The next approach we tried was to start from the lower bound:

*"If a tour with `O(n)` turns existed, what would it look like? And, if it is not possible, what exactly is the obstacle?"*

Understanding *what*, exactly, makes a problem hard, can lead to insights for how to address it.

So, we asked, *"what if none of the inner squares had a turns?" What if all the turns were along the edges?"*

We started drawing a tour that would only turn near the edges, like this, knowing that it would be practically impossible to actually finish it:

![Partial ideal tour](https://nilmamano.com/blog/knights-tour/aim_for_sky.png)

We learned that we could cover a compact chunk of the board this way, leaving only the edges to figure out later:

![Partial ideal tour](https://nilmamano.com/blog/knights-tour/aim_for_sky2.png)

Now, the *"only"* thing that was left to get a tour with `O(n)` turns was completing the the edges of the board. While obviously hard, it didn't seem outright impossible.

We started looking at ways of covering a narrow strip, and we found constructions like this, which consists of two separate path segments (red and blue):

![Partial ideal tour](https://nilmamano.com/blog/knights-tour/aim_for_sky3.png)

Since the previous image shows a way of covering an edge pattern with two path segments, we started exploring the idea of covering the main body of the board with multiple path segments as well. Here's an example with 3 path segments:

![Partial ideal tour](https://nilmamano.com/blog/knights-tour/aim_for_sky4.png)

## A happy idea

At this point, we still didn't have anything concrete, but we kept exploring patterns.

We found that using **4** path segments seemed to fill the board with a pretty regular shape:

![Partial ideal tour](https://nilmamano.com/blog/knights-tour/aim_for_sky5.png)

It was looking at this that we hit on the **key abstraction** that made the whole project fall into place:

A `2x2` formation of knights moves kind of like a king. That is, four knights
can make straight moves (up, down, left, right) or diagonal moves without
leaving any gaps in between.

![Formation moves](https://nilmamano.com/blog/knights-tour/formation_moves.png)

What makes the knight case hard compared to a king is that, when it moves, it leaves "gaps" that need to be filled later. But this formation solves this problem!

We now had a clear direction: instead of traversing the board with a single knight, we'd traverse it with a formation of four knights.
Then, somewhere, like in a corner of the board, we'd reserve a special region to tie together the four knights into a single path.

Obviously, we still need to work out the "tie together" part, but that seemed very doable.

Unlike the divide-and-conquer approaches, this new approach is actually great for minimizing turns. Straight formation moves (up, down, left, right) introduce turns, so they are no good, but consecutive diagonal moves in the same direction do not. Thus, our approach to minimize turns consisted on maximizing long sequences of diagonal moves, resulting in this zig-zag pattern across the board:

![Formation path](https://nilmamano.com/blog/knights-tour/formation_path.png)

And this can be tied together into a single tour by filling in the corners carefully:

![Full tour](https://nilmamano.com/blog/knights-tour/full_tour.png)

## Figuring out the corners

One challenge is that different board dimensions require different corner patterns, so we had to put some attention to detail when proving that the construction works for all dimensions.

Eventually, we showed that we can handle any board dimensions with some combinations of the following corner patterns:

![Corner patterns](https://nilmamano.com/blog/knights-tour/corners.png)

You can try different dimensions in our interactive demo here: [nmamano.github.io/MinCrossingsKnightsTour](https://nmamano.github.io/MinCrossingsKnightsTour/index.html).

This is formalized as Algorithm 1 in the paper (along with a formal proof that it always forms a complete tour).

With it, we now had our holy grail: a tour with `O(n)` turns and crossings, since all turns and crossings happen along the edges, which contain `O(n)` cells. This matches our lower bound, at least asymptotically, defeating my intuition that it was impossible.

Now, if you just read the paper, you'd think that plugging in the right corners was straightforward. And, to be clear, finding corners that work is not too hard. But we still spent a lot of time figuring out the cleanest way to handle them. Here is a collage of sketches we shared in the project's group chat--and it's not all of them:

![Corner attempts](https://nilmamano.com/blog/knights-tour/collage.png)

I could make another collage for how to handle the bottom-right and top-left corners, which we covered with formation moves. For instance, here is some case analysis we did for how to handle these corners for different rectangular board dimensions:

![Case analysis for corners](https://nilmamano.com/blog/knights-tour/case_analysis_corners.png)

This case analysis used "square" corners in the bottom-left and top-right corners, which we ended up not using in the paper.

Like the tip of an iceberg, a paper hides most of the work that goes into
making it.

## Generalizations

When presenting a new idea in a paper, it is a good idea to ask *"what other problems can be solved with this idea? can it be generalized to other problems?"* This is a good way to make your paper stronger and increase your chances of getting through peer review.

In our case, it seemed clear that our idea should be able to handle rectangular boards, so, when we formalized the algorithm, we made it in a way that works for any dimensions where a tour exists (i.e., where the dimensions are not too small and at least one dimension is even).

But we didn't stop at rectangular boards. Since we had to go through the literature on the knight's tour problem to make sure our idea was new, as we did, we looked at all the variants that people have addressed in the past. Then, we used our knight formation idea to tackle those as well:

- **Tours on boards with three and higher dimensions.** Here you can see the 4-knight formation moving from one layer of a 3D board to the next:

![3D tour](https://nilmamano.com/blog/knights-tour/3d.png)

(This figure sent me on a side quest to figure out perspective drawing in a 2D drawing editor).

- **Tours that are symmetric under 90 degree rotations.** We did this by stitching together four copies of our tour:

![Symmetric tour](https://nilmamano.com/blog/knights-tour/symmetric_tour.png)

- **Tours for "giraffes"**, which move one square in one direction and 4 in the other. This one is funny because it involves a formation of 16 giraffes:

![Giraffe formation](https://nilmamano.com/blog/knights-tour/giraffe_formation.png)

Transition from one diagonal to the next with 16 giraffes is kind of an ordeal:

![Giraffe transition](https://nilmamano.com/blog/knights-tour/giraffe_transition.png)

And making sure that the corners tied the 16 giraffes together into a single path was impossible to do by hand. I coded a backtracking algorithm to crack it.

![Giraffe corners](https://nilmamano.com/blog/knights-tour/giraffe_corners.png)

Behold, the ultimate monster:

![Giraffe tour](https://nilmamano.com/blog/knights-tour/giraffe_tour.png)

Anyway, enough *horsing around*...

We essentially covered the main variations discussed in the literature. In each case, we mostly had to make tweaks about how to handle corners, but the main idea held well. To me, this suggests that our technique should be the go-to approach for the knight's tour problem even when you don't care about turns and crossings, but I may be biased ;)

Besides these variations, to further strengthen our paper, we also showed that our algorithm was not only efficient (running in linear time) but also highly parallelizable.

## Approximation ratios

As we mentioned, the number of turns on an `nxn` board, `O(n)`, is asymptotically optimal. That is, our tour is within a constant factor of the optimal number of turns.

However, we can refine that: what is the exact number? and how close is that to the optimal number?

The first question is straightforward: we calculate how many zig-zags the formation makes as a function of `n`, and then multiply that by the number of turns made by the formation each time it transitions to the next diagonal. In total, we get `9.25n + C` turns, where `C` is some small constant.

The second question is much more difficult. To know how far we are from the optimal number, we would need the optimal tour, which we obviously don't have. Instead, if we can find some *lower bound* on the number of turns, then the ratio between the lower bound and our count gives us an *approximation ratio* of how far off we are from the optimal number in the worst case.

We already discussed a trivial lower bound: every cell along the edge of the board *must* be a turn, so we have at least `4n - 4` turns.
However, the higher we can take it, the better our approximation ratio will look.

We were able to prove a lower bound of `5.99n`. That is, no matter the approach, there must be at least `5.99n` turns in *any* knight's tour. (The exact statement is: for any `ε > 0`, there exists an `n0` such that, for all `n > n0`, a knight's tour on an `nxn` board has at least `(6 - ε)n` turns.)

The proof is a bit convoluted, but it comes from a simple intuition (as is often the case...). Take all `~4n` edge cells. Each one has two "legs": sequences of aligned moves coming out of it. The legs end when they either (a) reach another edge of the board, or (b) run into something that prevents them from reaching it. The idea is that the `~8n` legs running across the board make the board too crowded and eventually some of them "crash" into each other, creating new turns that are not at edge cells. We show that there must be at least `~2n` "crashes", bringing the lower bound up to `~6n`.

I won't get into why (you can see the paper), but I found it pretty unexpected that the proof involves a fractal, so I'll just show the fractal here out of context:

![Lower bound fractal](https://nilmamano.com/blog/knights-tour/lower_bound_fractal.svg)

Combining the upper and lower bounds, we get an approximation ratio of `~9.25/6`. A pretty small gap!

So, what do I think is the *actual* optimal number? I'm really not sure, but I
think it will be easier to raise the lower bound than to lower the upper
bound.

Eventually, we circled back to the original problem of minimizing crossings, and we were able to show an approximation ratio of `~3` in that case. Our construction has `~12n` crossings, and the best lower bound we were able to show is `~4n`. (This lower bound seems like low hanging fruit for improvement, if anyone is looking for a problem to work on!)

## Unexpected help

One day, I received the most random (and delightful) of emails: a student from a class I TA'd, Parker Williams, sent me an improvement to our approximation ratio out of nowhere. We had never discussed collaborating on this.

The email read:

> Hi Nil,
>
> I had a look at the heel in the open problems doc and I couldn't help myself, here are all possible tours for the "small heel" (there are possible improvements for both turns and crossings!) the one used in the paper is the fourth one down:
>
> ![Heels found by Parker](https://nilmamano.com/blog/knights-tour/parker_email.png)
>
> I found this list by searching the problem space exhaustively, I was expecting it to take too long and that maybe a greedy/DP type algorithm would be necessary but the whole search actually finished in less than a second in python on a laptop.
>
> [...]
>
> Are any of the small heel findings valuable? I understand it's a very marginal improvement in upper bound [...].

Yes, *yes, they are!* Parker's optimized diagonal transitions improved our upper bounds from `~9.5n` turns and `~13n` crossings to `~9.25n` turns and `~12n` crossings (as mentioned above), tightening the approximation ratios a bit further.

By that point, we had already published the paper in a conference called [FUN](https://sites.google.com/view/fun2020/acceptedpapers) (short for "Fun with algorithms"), but we had been invited to publish a journal version in [TCS](https://en.wikipedia.org/wiki/Theoretical_Computer_Science_(journal)), so we added Parker's results to the journal version and added him as a co-author.

Still one of my favorite emails I've ever received.

I hope this post helped demystify CS theory research a bit--even if it is for a silly puzzle that originated at tea time. I may summarize it as: it's not as hard as it seems, but it is more work than it seems. So, enjoying the process and having fun is probably more important than being a genius.

*Want to leave a comment? You can post under the [linkedin post](https://www.linkedin.com/posts/nilmamano_new-blog-post-lifecycle-of-a-cs-research-activity-7324858118490742784-LeR3?utm_source=share&utm_medium=member_desktop&rcm=ACoAAC6jqIwBADV70xmTEpmkxbAnN_32mssoxA8) or the [X post](https://x.com/Nil053/status/1919091615194353890).*






# [Why Many Greedy Algorithms Are Pickier Than They Need To Be](https://nilmamano.com/blog/greedy-algorithms)

![Why Many Greedy Algorithms Are Pickier Than They Need To Be](https://nilmamano.com/blog/greedy-algorithms/cover.png)

The image below shows four problems from completely different domains. A possible solution to each is shown in red.

![Greedy for hierarchical clustering, TSP, shortest superstring, and matching.](https://nilmamano.com/blog/greedy-algorithms/gleexamples.png)

The solutions in red are not just any solution. They are the results of well known greedy algorithms for each of these problems. Greedy algorithms, soon to be covered in detail, follow intuitive rules: in clustering, cluster together the two closest points. In routing, use the shortest edge in your route. In shorest superstring, combine the two strings that overlap the most. In matching, assign together the worker and task with the cheapest cost.

This article is not about any of these algorithms in particular, but about something they have in common. We will take a look at greedy algorithms like those above and see that it is often possible to design alternative algorithms (what I will call local greedy algorithms below) with "weaker" selection rules that somehow still end up with the same solution. The meaning of this will become clear in time. This observation changed my understanding of greedy algorithms and led to many of the results in my research. I dedicated chapter 2 of [my thesis](http://nilmamano.com/thesis/nilthesis.pdf) to it. This article presents the main takeaways from that chapter and illustrates them with plenty of examples without getting into the weeds.

**Scope:** this article is intended for people interested in algorithm design. It only requires a basic understanding of algorithms, as I tried to keep it self-contained *except for the references*, which can be found in my thesis (Disclaimer: I will shamelessly not include any references here). The article begins explaining greedy algorithms and this idea of "weakening" their selection rules. We will then look at standard greedy algorithms for 6 different problems, analyze their selection rules, and find ways to weaken them. Half-way through, once we have built some intuition, I explain the necessary conditions for this to be possible. Since the greedy algorithms I consider are not new, I will not get into their runtimes or approximation ratios here. This, again, can be found in the references. I hope you find it interesting!

## Greedy algorithms

Greedy algorithms are perhaps the most common way to approach optimization problems. They can be used in a broad class of problems where the input is a set of elements which need to be arranged into a solution. The input elements could be nodes in a graph, points in space, strings, tasks to be scheduled... The structure of the solution depends on the problem: perhaps we need to select a subset of the input elements, order them, group them in some fashion... Many optimization problems can be defined by just two things: a criteria that determines what constitutes a valid solution, and an objective function among valid solutions. The goal is to find a valid solution optimizing the objective function.

We focus on problems of this type. A classic example is the [*maximum-weight matching problem*](https://en.wikipedia.org/wiki/Matching_(graph_theory)#Maximum-weight_matching) (MWM): Given an undirected graph with weighted edges, find a matching (a pairing of the nodes such that each node is in at most one pair) of maximum weight.

Greedy algorithms are often employed for this kind of combinatorial problems because they have an exponential number of potential solutions. For instance, the number of different subsets of a set of *n* elements is *2^n*, while the number of orderings is *n!*. Thus, brute force search is too expensive.

The greedy approach is to construct a solution one component at a time. At each step, we consider a set of legal choices that allow us to make progress towards a solution. Among those, we choose the one that seems best according to an *evaluation function*. This function, which the algorithm designer must devise, should evaluate the utility of each choice, i.e., how "desirable" it appears in terms of reaching a good solution. Using the right evaluation function is key for the success of a greedy algorithm. The name *greedy* comes from the fact that once a choice is made, that choice is permanent; in algorithmic terms, there is no backtracking. Given its nature, a greedy algorithm should only consider "legal" choices in the sense that they should always lead to a final solution that is valid. However, a choice that seem best at an early stage (according to the evaluation function) may turn out to be suboptimal. This is why, in general, greedy algorithms are not guaranteed to find the optimal solution.

In the MWM example, a greedy algorithm constructs a matching one edge at a time. At each step, it chooses the edge with the maximum weight among the valid edges (edges that do not connect already matched nodes). While this greedy algorithm is not optimal, its approximation factor is 1/2, meaning that the weight of the resulting matching is guaranteed to be at least half the weight of the optimal one.

Here is an example execution of the Greedy for MWM in a geometric setting. Nodes are points in the plane and every pair of points is connected by an edge with weight proportional to their proximity (closer nodes have higher weight). The greedy algorithm repeatedly matches the closest available pair.

![Greedy for Maximum-weight matching](https://nilmamano.com/blog/greedy-algorithms/greedy_matching.gif)

## Local Greedy

As mentioned, only two ingredients are necessary to design a greedy algorithm: a way to construct a valid solution by making a sequence of choices, and an evaluation function to rank the choices at each step.

Using these same two elements, we will design a variant of the greedy strategy that we call *local greedy*. As in a greedy algorithm, a local greedy algorithm constructs a solution by making an irrevocable choice at each step. However, we *relax* the condition that we must pick the best choice at each step. In order to define the new criteria for picking a choice, we need one more ingredient: a notion of *interaction* between the available choices at each step. Two choices can interact in two ways. First, in terms of validity: often, making a choice means that another choice stops being compatible with a valid solution. Second, in terms of *utility*: making a choice might make another one less or more desirable according to the evaluation function. Since not all pairs of choices necessarily interact, this relationship defines an *interaction graph*: a graph with the set of valid choices as nodes and where edges represent interaction.

In the greedy for MWM, two edges interact if they share an endpoint, because picking one invalidates the other. For other greedy algorithms, the interactions depend on the problem *and* the evaluation function.

Given the interaction graph, we can define the local greedy algorithm. For simplicity, assume that there are no ties in the evaluations of the choices. We call the choice with the highest evaluation *globally dominant*. We call a choice *locally dominant* if it has a higher evaluation than its neighbors in the interaction graph. Whereas the standard greedy algorithm makes the globally-dominant choice at each step, local greedy makes *any* of the locally-dominant choices. Note that there is a unique globally-dominant choice, while there can be multiple locally-dominant ones. The globally-dominant choice is also locally dominant, but the converse is not necessarily true. Henceforth, we refer to the standard greedy algorithm as global greedy (GG) to distinguish it from local greedy (LG).

Even if GG and LG operate over the same set of choices and with the same evaluation function, they have two remarkable differences: first, local greedy is non-deterministic. If there are multiple locally-dominant choices, any of them can be chosen. Thus, one can entertain different strategies for finding locally-dominant choices. In fact, GG is one such strategy, so GG is a special case of LG. The second difference, naturally, is its locality: to implement GG, one needs to know every choice in order to determine the globally-dominant one. In contrast, LG can make a choice while being only aware of its neighbors. The extra freedom and locality are promising angles of attack for the design of algorithms, particularly in distributed and parallelized settings.

We can turn the Greedy algorithm that we saw for MWM into LG: at each step, choose any edge `e={u,v}` such that *e* is heavier than any other edge touching *u* or *v*. Repeat until no more edges can be added.

Here is one of the possible runs of local greedy for the geometric version of MWM (the circles pairs are all the options LG can choose):

![Local Greedy for Maximum-weight matching](https://nilmamano.com/blog/greedy-algorithms/local_greedy_matching.gif)

## Global-Local Equivalence

At first glance, LG seems like a downgrade from GG: at best, the choices of LG are as good as those of GG, but they can also be worse (according to the evaluation function). This article is about an observation that was surprising to me: **for many greedy algorithms, local greedy produces the same solution as global greedy.** (Disclaimer: This is not entirely new, as it was already known for some specific problems, including MWM. However, to my knowledge, it had not been treated as a general phenomenon before my work. See a discussion on related work in my thesis.) We coin the term *global-local equivalence* (GLE) for greedy algorithms with this property. A consequence of global-local equivalence is that *every run of local greedy produces the same solution*, the global greedy solution, regardless of the order in which the choices are made.

Not all greedy algorithms exhibit GLE. We will see examples of both and understand the key difference.

## Maximum-weight matching

As mentioned, MWM is one of the problems with GLE. Here we can see that even though the orderings differ, the final matching in the previous example is the same:

![Global-local equivalence for Maximum-weight matching](https://nilmamano.com/blog/greedy-algorithms/gle_matching.png)

I claimed I wouldn't get into proofs, but the proof of GLE for the MWM Greedy is really neat and short so I'll just leave it here.

**Lemma:** Let *G* be an undirected graph with unique edge weights. Let *M1, M2* be any two matchings in *G* obtained by the local greedy algorithm for MWM. Then, *M1=M2*.

**Proof:** Assume, for a contradiction, that *M1* differs from *M2*. Let *e* be the heaviest edge in one (without loss of generality, *M1*) but not the other (*M2*). During the course of the algorithm, every edge is either added to the matching or invalidated because a heavier neighbor was picked. Since *e* is not in *M2*, *M2* contains a neighbor edge *e'* of *e* that is heavier than *e* (see the figure below). However, *e'* cannot be in *M1* because *e* is in *M1*. This contradicts the assumption that *e* was the heaviest edge in only one of the matchings. That completes the proof.

![Proof of local-global equivalence for matching.](https://nilmamano.com/blog/greedy-algorithms/proof_gle_matching.png)

Since any two runs of LG find the same solution, and GG is a special case of LG, it follows that every run of LG finds the same solution as GG.

I'll take a quick detour into the story of GLE for MWM. Before it was discovered, LG was proposed as a "new" algorithm and it was proven that it achieves a 1/2 approximation ratio, just like Greedy (of course, they achieve the same approximation ratio because they find the same solution). A funny thing I found is that there is a paper doing an empirical comparison of the solution quality of different MWM algorithms, and it includes the traditional Greedy and LG as different algorithms. **They compared two things mathematically proven to be the same.** In the experiment, they actually obtain slightly different results for the two, which must come down to handling ties differently. Had they used consistent tie-breaking rules in both implementations, they would have got the exact same numbers, probably rising some questions. Here is the table from their paper (LG is labeled LAM):

![Comparison of MWM algorithms](https://nilmamano.com/blog/greedy-algorithms/empiricalcomp.png)

## Set Cover

[Set cover](https://en.wikipedia.org/wiki/Set_cover_problem) is another classic NP-complete optimization problem: Given a set *U* and a collection *X* of subsets of *U* with positive weights, find a cover of *U* of minimum weight. A *cover* is a subset of *X* such that every element of *U* is contained in one of the sets.

Set cover has some important special cases such as vertex cover.

The image below shows a set cover instance: on the left, we have a visual representation of the elements in *U* and the subsets they belong to. On the middle, the same instance is represented as a bipartite graph where the edges denote that the element belongs to the set. On the left, we have the "interactions" between the sets: two sets interact if they have an element in common.

![Set cover instance](https://nilmamano.com/blog/greedy-algorithms/setcover.png)

There is a well known Greedy for set cover which picks one set a time until all the elements are covered. It uses an evaluation function known as *cost-per-element*. The cost-per-element of a set is the weight of the set divided by the number of still-uncovered elements in it (or infinite, if they are all covered). Greedy always picks the set minimizing the cost-per-element.

To define LG, we need to start with the interactions: two sets interact if they have an element in common because picking one increases the cost-per-element of the other. Based on this, a set is locally dominant if it has a smaller cost-per-element than any other set with an element in common. LG constructs a cover by repeatedly picking a "locally-dominant" until every element is covered.

Again, we have global-local equivalence in Set Cover. That is, GG and LG always end up with the same cover. To prove it, we cannot use the simple argument we saw for MWM. That proof relies on the ability to identify the heaviest edge where two matchings differ. However, the cost-per-element of the sets depend on the current partial solution, so the evaluations evolve over time. This makes it impossible to pinpoint the first discrepancy. I will later talk about how we proved GLE for set cover and other problems with changing evaluations.

Now, let us look at a greedy algorithm *without* GLE.

## Maximum-weight Independent Set

In the Maximum-weight Independent Set (MWIS) problem, we are given an undirected graph with weighted nodes, and the goal is to find an [independent set](https://en.wikipedia.org/wiki/Independent_set_(graph_theory)) of maximum weight. An independent set is a subset of nodes such that no two nodes in the subset are neighbors.

A Greedy for the unweighted case (all nodes have the same weight) starts with an empty solution and adds nodes to it one by one. Since when we add a node to the solution none of its neighbors can be added in the future, the selection rule is to always pick the node that "invalidates" the fewest neighbors. That is, neighbors not in the solution nor with a neighbor in it.

This intuition can be generalized to the weighted case as follows: the Greedy for the weighted case chooses the node maximizing its weight divided by the number of valid neighbors (including itself).

Thinking in terms of the interaction graph, picking a node changes the evaluation of the nodes at distance 1 (they become invalid) and at distance 2 (their evaluation improves, because they invalidate one fewer neighbors). Thus, we can turn this Greedy into LG: pick any node that has a better evaluation than any other node within distance 2.

However, this local greedy does *not* necessarily produce the same solution as the Greedy. The next example proves that this Greedy does not have GLE:

![Maximum-weight Independent Set Instance](https://nilmamano.com/blog/greedy-algorithms/mis.png)

The nodes are labeled with their weights. The edges of the graph are shown in black, and the edges of the interaction graph are shown dashed in blue. Below each node, their initial evaluation is shown in red. Initially, the locally-dominant nodes are the ones with weight 5 and 8. GG chooses the node with weight 8 first, and then (after readjusting the evaluations), the node with weight 6. In contrast, LG could start by picking the node with weight 5, resulting in a different final solution, *8*.

I do not mean to imply that LG is not "good" without GLE -- only that the solution may differ. In this particular case, even though we do not have GLE, GG and LG guarantee the same approximation ratio. I'll defer to my thesis for more details. Also in my thesis are other Greedys for MWIS that *do* have GLE, showing that GLE is not only about the problem, but also about the evaluation function.

## So WHEN do we have Global-Local Equivalence?

What is the common structure that MWM and set cover have, but MWIS does not? What is the key to GLE?

One of my favorite results from my PhD is that there is a simple rule for when we have GLE: informally, the key is that *the evaluation of the choices must stay the same or get worse over the course of the algorithm*. In other words, it should never get better. The intuition is that if a choice, say, *C*, is better than all its neighbors in the interaction graph (what we call locally dominant) and its neighbors can only get worse as a result of other choices made by the algorithm, then *C* will remain locally dominant until it is eventually picked. Of course, its neighbors won't be picked before *C*, because they cannot be locally-dominant while *C* is present. Conversely, if the choices *can* get better over time, then a neighbor of *C* could become better than *C* and *C* would stop being locally-dominant, and it may end up not being picked.

We were able to capture this intuition in a single theorem, from which all the results we have seen follow:

**Theorem 2.9** [*page 20*](http://nilmamano.com/thesis/nilthesis.pdf). Let *h* be a deteriorating evaluation function for a combinatorial optimization problem. Then, the global and local greedy algorithms based on *h* output the same solution.

If it's not clear from the context, "deteriorating" evaluation functions are those where the evaluations of the choices cannot get better. Let's review the examples we have seen:

- Maximum-weight matching: we select edges based on their weights, which do not change until they are picked or become invalid, so the evaluation function is deteriorating.
- Set cover: as sets are added to the solution, the evaluation of the remaining sets stays the same or gets worse because there are fewer remaining elements to cover and their cost-per-element goes up. Thus, the evaluation function is deteriorating.
- Maximum-weight independent set: as nodes are picked, the evaluation of the remaining nodes *can* go up. For instance, if a node *v* has a neighbor that is invalidated by another neighbor, the evaluation of *v* goes up because now *v* invalidates one fewer neighbor. Thus, the evaluation function is not deteriorating.

I'll omit the proof to avoid getting technical, but I'll recommend it to readers who enjoyed the proof for GLE for the MWM Greedy. It's an elegant argument (in my opinion) that considers a hypothetical hybrid algorithm that starts behaving as LG and at some iteration transitions to GG. We show that no matter where the switch happens, the final result is the same. Since GG and LG are at the two endpoints of this spectrum (GG corresponds to transitioning immediately, and LG corresponds to never transitioning), the theorem follows.

## The origin of GLE: Hierarchical Clustering

[Hierarchical clustering](https://en.wikipedia.org/wiki/Hierarchical_clustering) deals with the organization of data into hierarchies. Given a set of points, we can construct a hierarchy as follows: each point starts as a base cluster (a cluster is a set of points). Then, a hierarchy of clusters is constructed by repeatedly merging the two "closest" clusters into a single one until there is only one cluster left.

![Hierarchical Clustering instance](https://nilmamano.com/blog/greedy-algorithms/hc.png)

A key component of hierarchical clustering is the function used to measure distances between clusters. The image above illustrates the result for a set of points when using the minimum distance among points from different clusters (also known as single linkage) as the cluster-distance metric. Other popular metrics include maximum distance (or complete linkage), and centroid distance (the centroid of a cluster is the point with the average of the coordinates of all the points).

This process is called *agglomerative* or *bottom-up* hierarchical clustering (regardless of the cluster-distance metric used). It creates a hierarchy where any two clusters are either nested or disjoint.

Our work on GLE was inspired by previous work on agglomerative hierarchical clustering. A kind of LG was proposed in the 80's as a way to speed up the construction. Instead of always merging the closest pair of clusters, LG merges any two clusters which are closer to each other than to any third cluster, also known as mutual nearest-neighbors (MNN). They discovered that GLE holds for agglomerative hierarchical clustering, but *only for some cluster-distance metrics*.

For example, we have GLE with single-linkage and complete-linkage, but not with centroid distance, as shown in the example below. The hierarchies found by GG and a possible run of LG for the point set on the left, using centroid distance, differ. The points *a* and *b* are the closest pair, while *c* and *d* are MNN. The centroids of the inner clusters are indicated with red crosses.

![Local vs global greedy for hierarchical clustering](https://nilmamano.com/blog/greedy-algorithms/noglehc.png)

They found that there is no GLE if a new cluster resulting from a merge can be closer to other clusters than both of the original clusters before the merge. For instance, in the example above, the centroid of *c* and *d* is closer to *b* than both *c* and *d*. This is why there is no GLE. In contrast, using minimum-distance instead, a new cluster is as far from the other clusters as one of the original clusters were. Thus, we get GLE.

The intuition is the same as we saw for combinatorial optimization problems: if new clusters cannot get closer to other clusters, then the merges done by the algorithm cannot "break" existing mutual nearest-neighbors, and they will *eventually* be picked. MNN are like locally-dominant pairs of clusters.

Unfortunately, this line of work on GLE died out in the 80's and never branched out beyond hierarchical clustering. In parallel, GLE was discovered for specific combinatorial problems like MWM, but no connection was drawn between the two.

## Travelling Salesperson Problem

The [Travelling Salesperson Problem](https://en.wikipedia.org/wiki/Travelling_salesman_problem) (TSP) is a famous NP-complete optimization problems at the root of most routing problems. One of its variants is Euclidean TSP: given a set of points in the plane, find a cycle going through all the points of minimum total length. The points can be seen as cities that must be visited by a salesperson.

Since TSP is computationally hard, a myriad of heuristic approaches have been proposed, including greedy algorithms. For instance, we can start at a random city and always go to the nearest unvisited city.

A greedy algorithm that seems to perform better in practice is the [*multi-fragment algorithm*](https://en.wikipedia.org/wiki/Multi-fragment_algorithm). Instead of growing the solution linearly, every node starts as a "fragment" of the solution. Then, the multi-fragment algorithm repeatedly finds the two closest fragments and connects them, creating longer fragments. The distance between two fragments, when they consist of more than one node, is the minimum distance between their endpoints. At the end, there is a single path going through every node. Then, the two endpoints are connected, closing the cycle.

Here is an animation of the multi-fragment algorithm. The gray nodes are those that are internal to a fragment and cannot be matched anymore. The closest pair of fragments at each step is highlighted in red.

![Greedy for TSP](https://nilmamano.com/blog/greedy-algorithms/greedy_tsp.gif)

This algorithm is very reminiscent of agglomerative hierarchical clustering.
We can say that two fragments are MNN if they are closer to each other than to any third fragment. Then, we can define a local greedy alternative algorithm which connects *any* pair of fragments which are MNN. Note that when we connect two fragments, the resulting fragment cannot be closer to a third fragment than either of the original fragments were. Thus, by a similar argument as we saw for hierarchical clustering, we have GLE.

Here is an animation of the LG algorithm. The dashed red loops highlight all the MNN that we *could* connect at each step. One of them is chosen arbitrarily.

![Local Greedy for TSP](https://nilmamano.com/blog/greedy-algorithms/local_greedy_tsp.gif)

The final cycle will be the same regardless of the choices we make:

![Global-local equivalence for TSP](https://nilmamano.com/blog/greedy-algorithms/gle_tsp.png)

## Shortest Common Superstring

Shortest Common Superstring (SCS) is an optimization problem over strings: given a set of strings, find the shortest string that is a superstring of all of them. A string is a superstring of another if it contains it consecutively, that is, without additional characters intertwined.

One of the killer applications of SCS is DNA sequencing. My (limited) understanding is that biologists have methods to *sample* short segments of a much longer DNA sequence, but they cannot pinpoint exactly where in the sequence the sample was extracted.

![SCS instance](https://nilmamano.com/blog/greedy-algorithms/scs.png)

They end up with a big pool of overlapping samples, and SCS is used to try to reconstruct the original sequence from the samples: if the end of a sample has a long matching sequence of characters with the beginning of another sample, it's statistically likely that they come from overlapping sections of the DNA sequence. The shortest common superstring is the string that contains all the samples and finds the most overlaps.

The problem is NP-hard, but some approximation algorithms are known. The most famous is a greedy algorithm simply known as Greedy (in our context, it corresponds to GG). This algorithm maintains a set of strings. Initially, this set is just the input set. Then, it repeatedly takes two strings in the set with the longest overlap and replaces them with the shortest superstring of both. We call this *merging* two strings. Greedy finishes when there is a single string left, which is returned.

![Greedy for SCS](https://nilmamano.com/blog/greedy-algorithms/greedy_scs.png)

This algorithm is similar to the multi-fragment algorithm for TSP, and, indeed, GLE also holds. Here, LG repeatedly merges *any* two strings which overlap more with each other than with any third string. It is harder to see, but we proved that the resulting merged strings do not overlap more with other strings than the original strings did before the merge.

![Local Greedy for SCS](https://nilmamano.com/blog/greedy-algorithms/local_greedy_scs.png)

I have shown some instances of GLE, but it would be interesting to find more (if someone knows or finds a greedy algorithm that might have GLE, please do reach out!)

I find GLE interesting on its own, but this article left unanswered a central question: once we have established that we have GLE, how do we actually use it to design faster algorithms? I'll leave that for a future entry (or, see the next chapter in my thesis).

One of our results is that you can use GLE to speed up the multi-fragment algorithm for Euclidean TSP from *O(n^2)* (a result from my own advisor 20 years ago) to *O(n log n)*. In other cases, like set cover and the shortest common superstring, we still haven't found a way to implement LG asymptotically faster than GG. However, my research focused on the sequential setting, and I think that GLE has even more potential in distributed and parallel algorithms, which I did not have time to explore much!

Finally, I will mention again that all the references for the problems and algorithms discussed here can be found [in my thesis](http://nilmamano.com/thesis/nilthesis.pdf). Many thanks to my colleagues Daniel Frishberg and Pedro Matias, and my advisors Michael Goodrich and David Eppstein, with whom I worked closely developing these ideas.



This blog post documents the initial design for the DB schema for the [Wall Game](https://nilmamano.com/blog/wall-game-intro), with commentary on the design choices.

**Disclaimer:** I haven't tested any of the SQL. The site has not been built
yet at the time of writing (March 2025). All the screenshots from the site are
from a prototype made with v0.dev as explained in [this
post](https://nilmamano.com/blog/wall-game-ui). As always, if you spot any mistakes or
improvements, I'd love to know!

The DB is a PostgreSQL database, though I aim to keep the schema as dialect-agnostic as possible in case I want to migrate in the future. (You can see [this post](https://nilmamano.com/blog/2025-stack) for a discussion on how I chose the tech stack.)

We'll start by designing all the tables, as shown in the diagram below, and then we'll write all the queries we need to support the frontend logic.

![Wall Game DB Diagram](https://nilmamano.com/blog/wall-game-db/diagram.png)

## Users

This is the main `users` table:

`users`
`CREATE TABLE users (
user_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
display_name VARCHAR(255) NOT NULL UNIQUE,
capitalized_display_name VARCHAR(255) NOT NULL,
auth_provider VARCHAR(255) NOT NULL, -- e.g., kinde, auth0
created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMPTZ,
is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
CONSTRAINT lowercase_display_name CHECK (display_name = LOWER(display_name))
);`

### Future-proofing auth-provider changes

I tried to future-proof it against auth-provider changes. The plan is to start using [Kinde](https://kinde.com), which means that the only thing we need to store in the DB is a unique user ID provided by Kinde (it looks something like `"kp_a1b2c3d4e5"`).

`"kp_a1b2c3d4e5"`

To avoid coupling, we don't want to use that as the user's primary id. A straightforward approach would be to put it in a separate field:

`CREATE TABLE users (
user_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
auth_user_id VARCHAR(255) NOT NULL UNIQUE,
...
);`

However, in a migration, it may be tricky to coordinate the change of `auth_user_id` from the old auth provider to the new one. Instead, I decided to just indicate the `auth_provider` in the `users` table (e.g., `"kinde"`) and put the `auth_user_id` in a separate table with primary key `(user_id, auth_provider)`:

`auth_user_id`
`auth_provider`
`users`
`"kinde"`
`auth_user_id`
`(user_id, auth_provider)`
`CREATE TABLE user_auth (
user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
auth_provider VARCHAR(255) NOT NULL,
auth_user_id TEXT UNIQUE NOT NULL, -- Kinde's user ID or other provider's ID
PRIMARY KEY (user_id, auth_provider)
);`

This way, a user can have, e.g., a Kinde key and an Auth0 key at the same time, and we can switch from Kinde to Auth0 by changing the `auth_provider` in the `users` table from `"kinde"` to `"auth0"` (without deleting the Kinde key yet).

`auth_provider`
`users`
`"kinde"`
`"auth0"`

### Handling unique usernames

We allow users to change their display name, and they are allowed to use uppercase letters, but, to avoid impersonation, we enforce that display name must be unique in a case-insensitive way.

We can think as the lowercase version of their display name as the "canonical" name, while the capitalized version is just an inconsequential styling choice. That's why we have both `display_name` and `capitalized_display_name` columns.

`display_name`
`capitalized_display_name`

In general, the plan is to keep validation logic in the backend, not in the DB. However, I'm particularly concerned about uppercase letters slipping through to the `display_name` field, so I added the constraint:

`display_name`
`CONSTRAINT lowercase_display_name CHECK (display_name = LOWER(display_name))`

### Encoding enum-like data

I've considered multiple ways of storing "enum-like" data like *auth providers*, *time controls* (which can only be "bullet", "blitz", "rapid", or "classical") or *variants* (which will start with only two options, but more will be added over time).

For example, if we have a column, `my_enum`, that can only have values `"aa"` and `"bb"`, we could do:

`my_enum`
`"aa"`
`"bb"`
`ENUM`
`"cc"`
`CREATE TYPE my_enum_type AS ENUM ('aa', 'bb');`
`VARCHAR`
`CHECK`
 `my_enum VARCHAR(255) NOT NULL CHECK (my_enum IN ('aa', 'bb'))`
`allowed_values`
`my_enum`
`CREATE TABLE allowed_values (
value VARCHAR(255) PRIMARY KEY
);
...
my_enum VARCHAR(255) NOT NULL REFERENCES allowed_values(value)
...`
`"aa"`
`CREATE TABLE allowed_values (
id SERIAL PRIMARY KEY,
name VARCHAR(255) NOT NULL UNIQUE
);
...
my_enum INTEGER NOT NULL REFERENCES allowed_values(id)
...`

In the end, I decided to [KISS](https://en.wikipedia.org/wiki/KISS_principle) and use a plain string column, and just be careful when inserting values.

## Rankings

ELO ratings are specific to a variant and time control, so we can't keep them in the `users` table.

`users`
`CREATE TABLE ratings (
user_id INTEGER REFERENCES users(user_id),
variant VARCHAR(255) NOT NULL, -- "standard" or "classic"
time_control VARCHAR(255) NOT NULL, -- "bullet", "blitz", "rapid", or "classical"
rating INTEGER NOT NULL DEFAULT 1200,
-- Precomputed fields by the backend:
peak_rating INTEGER NOT NULL DEFAULT 1200,
record_wins INTEGER NOT NULL DEFAULT 0,
record_losses INTEGER NOT NULL DEFAULT 0,
last_game_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMPTZ,
PRIMARY KEY (user_id, variant, time_control)
);`

### Optimizing the Ranking page

The final four columns in the `ratings` table are needed for the Ranking page (the `First Game` column in the prototype below will be replaced by `Join Date`):

`ratings`
`First Game`
`Join Date`
![Ranking](https://nilmamano.com/blog/wall-game-ui/v07.png)

These columns are redundant, as they could be computed by aggregating information from the
`games` table. However, it would be expensive to, e.g., look through all the games
of a user to find its peak rating. Instead, the plan is to precompute these columns
in the backend and update them whenever a user finishes a game.

The downside of this approach is that the `games` and `ratings` tables may be in an inconsistent state. For example, if a game somehow disappears from the `games` table, a player may end up with a "3-0" record even though they only have two games in the DB. I think this is OK. First, it's not clear what should happen if a game disappears--it doesn't retroactively change the fact that the player played three games. Second, we can always run a one-off query to fix the precomputed fields.

`games`
`ratings`
`games`

Instead of having the backend compute these fields, an alternative approach would be to have a cron job that updates them periodically. However, when a user reaches a new peak rating, they probably want it to be reflected immediately in the Ranking.

## Games

Games will only be stored in the DB when they are finished, which allows us to make more assumptions (all players joined, there is an outcome, etc.) and simplify the schema. The downside is that, if the server crashes, all on-going games will be lost. (I once mentioned this concern to a friend and he said, "But the server shouldn't crash." *Fair point...*)

`CREATE TABLE games (
game_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
variant VARCHAR(255) NOT NULL,
time_control VARCHAR(255) NOT NULL,
rated BOOLEAN NOT NULL,
board_width INTEGER NOT NULL,
board_height INTEGER NOT NULL,
started_at TIMESTAMPTZ NOT NULL,
views INTEGER NOT NULL DEFAULT 0,
-- Precomputed fields by the backend:
moves_count INTEGER NOT NULL DEFAULT 0
);`

### Optimizing the Past Games page

We split the game data into two. The main table, `games`, has all the "metadata" about the game, while the `game_details` table has the actual list of moves and configuration parameters (e.g., variant-specific parameters):

`games`
`game_details`
`CREATE TABLE game_details (
game_id INTEGER PRIMARY KEY,
config_parameters JSONB, -- Variant-specific game configuration parameters
moves JSONB NOT NULL, -- Custom notation for all moves
FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);`

The reason for the split is that the game details take a lot more space than the other fields, and the main use case for storing games is listing them on the "Past Games" page, which doesn't need the game details:

![Past Games](https://nilmamano.com/blog/wall-game-ui/v08.png)

The query for this page can be based on the `games` table only. The game details only need to be brought in when the user watches a specific game.

I'm really not sure if this is worth it, though. This may be a *premature optimization* that adds unnecessary complexity (the two tables now need to be kept in sync and updated together in transactions).

Another interesting decision was whether to store the moves in a SQL `moves` table or as a JSON blob. I decided to go with the latter because I don't have any need for querying individual moves within a game or across games. We'll always want either all the moves of a single game, or none. One downside is that we need to precompute the `moves_count` column in the `games` table.

`moves`
`moves_count`
`games`

### Game players

As you can see, the `games` table does not capture the players or the game outcome. The reason is that the number of players per game depends on the variant, so we couldn't simply have `player1` and `player2` columns. For the same reason, the outcome is not as simple as "P1 won" or "P2 won" or "draw". Instead, it makes more sense to think about *per-player outcomes*. Each player outcome consists of a *placement* and a *reason*. E.g., a player may have finished 3rd for the reason that the 4th player timed out.

`games`
`player1`
`player2`

The following table connects games and players:

`CREATE TABLE game_players (
game_id INTEGER REFERENCES games(game_id),
player_order INTEGER NOT NULL, -- 1 for the 1st mover, 2 for the 2nd mover, etc.
player_config_type VARCHAR(255) NOT NULL, -- "you", "friend", "matched user", "bot", "custom bot"
user_id INTEGER REFERENCES users(user_id), -- NULL for non-logged-in users and built-in bots
bot_id INTEGER REFERENCES built_in_bots(bot_id), -- Only non-NULL for built-in bots
rating_at_start INTEGER, -- Rating at game start, NULL for custom bots
outcome_rank INTEGER NOT NULL, -- e.g., 1 for winner
outcome_reason VARCHAR(255) NOT NULL, -- "timeout", "resignation", "knockout", "agreement", "tie", "abandoned"
PRIMARY KEY (game_id, player_order)
);`

As we discussed [earlier](#handling-unique-usernames), handling username changes is tricky. If you are watching a past game, do you want to see the current name or the name at the time of the game? In our case, we won't bother with historical names, so we don't need a `player_name_at_the_time` column. The same for the pawn color and shape they chose at the time. On the other hand, we *do* want to know their ELO at the time.

`player_name_at_the_time`

### Bots

Let's discuss the workflow for built-in bots. Besides the main backend, there is a *bot service* responsible for making bot moves. The main backend stays focused on I/O tasks and doesn't hang on long computations.

The steps go like this:

`bot_id`
`bot_id`
`bot_id`
`built_in_bots`
`CREATE TABLE built_in_bots (
bot_id VARCHAR(255) PRIMARY KEY,
-- Fields should not be changed after creation
-- e.g., "Easy Bot", "Medium Bot", "Hard Bot". Not unique. Uppercase allowed.
display_name VARCHAR(255) NOT NULL,
metadata JSONB -- metadata provided by the bot service (e.g., compilation flags)
);`

The bot service is responsible for choosing and managing bot IDs. The idea is that they should identify a specific algorithm/implementation/binary/version. That is, if I train an improved version of the "Hard Bot", the display name can stay the same, but the `bot_id` should be different.

`bot_id`

The backend and the DB don't need to know which `bot_id`'s can play in which variants and things like that. The backend doesn't ask the DB for which bots are available--it asks the bot service. So, there is no `variant` column and such in the `built_in_bots` table.

`bot_id`
`variant`
`built_in_bots`

### Custom bots

Custom bots are not fully designed yet, but, for an initial design, we don't need a table for custom bots. When a user chooses to play against their own custom bot, the user is given a token to join the game from their bot client. The client only provides moves (as if it were a human), and does not have its own display name or bot id (to avoid having to deal with clashes with real users or built-in bots). The display name can always be "Custom Bot".

In a full-fledged custom bot system like the one on [Lichess](https://lichess.org/@/lichess/blog/welcome-lichess-bots/WvDNticA), custom bots are just like [regular users](https://lichess.org/player/bots) (with some limitations). Anyone can list their bot, and then players can invite them to a game and they'll join just as if you invited a regular user. This is out of scope.

## Puzzles

A puzzle is a game that has been setup to a specific situation where there is a good move (or sequence of moves) that the user must find. Here is Puzzle 10 from the first version of the site, [wallwars.net](https://wallwars.net):

![Puzzle](https://nilmamano.com/blog/wall-game-db/puzzle.png)

Here is the main `puzzles` table. The specific initial configuration (pre-existing walls and player positions) is part of the game parameters.

`puzzles`
`CREATE TABLE puzzles (
puzzle_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
title VARCHAR(255) NOT NULL,
description TEXT NOT NULL,
puzzle_list VARCHAR(255) NOT NULL, -- "solo_campaign" or "puzzles"
list_index INTEGER NOT NULL, -- Position of the puzzle within its list, for ordering
rating INTEGER NOT NULL, -- Difficulty rating of the puzzle, in ELO
config_parameters JSONB, -- Puzzle setup (e.g., variant, pre-existing walls and player positions)
puzzle_metadata JSONB, -- Additional metadata about the puzzle
author VARCHAR(255) NOT NULL, -- Puzzle author (not a user)
creation_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);`

To track completions:

`CREATE TABLE user_puzzles (
user_id INTEGER REFERENCES users(user_id),
puzzle_id INTEGER REFERENCES puzzles(puzzle_id),
attempted_at TIMESTAMPTZ, -- NULL if not attempted
completed_at TIMESTAMPTZ, -- NULL if not completed
PRIMARY KEY (user_id, puzzle_id)
);`

A complication with the Wall Game (compared to, e.g., chess) is that there are often many moves that achieve the same effect. E.g., if there is a long 'tunnel' that is one row wide, putting *any* wall along the tunnel has the same effect of blocking it. There can be 100's of equally good moves in realistic situations. Thus, we cannot simply check whether the user finds the "correct" move.

Instead of "hard-coding" the solution, we can compare the user's move against the moves of a bot which is smart enough to solve the puzzle. If the bot scores the player's move as tangibly worse than its top choice, the move is considered wrong. The same bot also counters the player's moves. This goes on until the game ends (the player wins or draws) or until the user has made a predetermined number of moves (which can be specified in the `puzzle_metadata`). If necessary, we can experiment with fine-tuning the baseline AI to solve specific puzzles. We'll see.

`puzzle_metadata`

For now, we don't support user-created puzzles.

The final tables store the user settings.

`CREATE TABLE user_settings (
user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
dark_theme BOOLEAN NOT NULL DEFAULT TRUE,
board_theme VARCHAR(255) NOT NULL DEFAULT 'default',
pawn_color VARCHAR(255) NOT NULL DEFAULT 'default',
default_variant VARCHAR(255) NOT NULL DEFAULT 'standard', -- "standard" or "classic"
default_time_control VARCHAR(255) NOT NULL DEFAULT 'rapid', -- "bullet", "blitz", "rapid", or "classical"
default_rated_status BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE user_pawn_settings (
user_id INTEGER REFERENCES users(user_id),
pawn_type VARCHAR(255) NOT NULL, -- "cat", "mouse", "goal", etc.
pawn_shape VARCHAR(255) NOT NULL, -- A sprite/icon identifier that the backend should recognize.
PRIMARY KEY (user_id, pawn_type)
);
CREATE TABLE user_variant_settings (
user_id INTEGER REFERENCES users(user_id),
variant VARCHAR(255) NOT NULL,
default_parameters JSONB NOT NULL, -- Variant-specific default parameters
PRIMARY KEY (user_id, variant)
);`

## Queries

The following queries power the functionality we need for the site.

The landing page shows a showcase from a past game, which autoplays the moves. This requires pulling a random game from the DB, including the moves.

![Showcase](https://nilmamano.com/blog/wall-game-ui/v01.png)

We can get it with this query:

`SELECT g.game_id, g.variant, g.time_control, g.rated, g.board_width,
g.board_height, g.started_at, g.moves_count, gd.config_parameters,
gd.moves
FROM games AS g
JOIN game_details AS gd USING (game_id)
ORDER BY RANDOM()
LIMIT 1;`

To reduce DB queries, the backend could send the same showcase game to multiple users.

### Solo campaign & Puzzles

When the user goes to the 'Solo Campaign' page, they can see an ordered list of "levels" (i.e., puzzles) in order. Each level has a name, description, difficulty, and completion status.

![Showcase](https://nilmamano.com/blog/wall-game-ui/v02.png)

We can pull them with this query:

`-- :user_id is the user's ID
SELECT p.puzzle_id, p.list_index, p.title, p.description, p.rating,
p.config_parameters, p.puzzle_metadata, up.completed_at
FROM puzzles AS p
LEFT JOIN user_puzzles AS up
ON p.puzzle_id = up.puzzle_id AND up.user_id = :user_id
WHERE p.puzzle_list = 'solo_campaign'
ORDER BY p.list_index;`

The 'Puzzles' page is similar.

We include `p.config_parameters` and `p.puzzle_metadata` in the query so that, when the user clicks on a puzzle/level, we have everything we need to set it up and start playing.

`p.config_parameters`
`p.puzzle_metadata`

### Available games

Players can see a list of games in the matchmaking stage, where the user is waiting for an opponent.

![Showcase](https://nilmamano.com/blog/wall-game-ui/v04.png)

We *won't* use SQL for this. These games haven't finished yet, so they are not in the DB--only in the backend.

### Implementing pagination and filtering

The 'Ranking' and 'Past Games' pages allow the user to essentially inspect the `ranking` and `games` tables, respectively, with *pagination* and *filtering*. This gives rise to a basic yet tricky software architecture question:

`ranking`
`games`

Suppose you have a full-stack app and there is a large table in the DB, which
the user can browse in the frontend. We show the user 100 rows at a time, and
they can navigate to the next or previous 100 rows. How do you implement this
pagination? (We could ask the same about filtering.)

Assumptions:

You have 3 main options for *where* to implement pagination:

At the **DB** level: this is slow, as it requires a DB round-trip every time the user wants to see a new 100-row block, but it guarantees the data is never stale and the backend can remain stateless. We can add a table index on the 'rank' column to speed up the query.

At the **backend** level: if the backend maintains a cached copy of the table (say, as an array), it can return the appropriate range of the array to the frontend, avoiding the DB. This introduces the problem of how to keep the backend's copy of the table always synced with the DB and sorted by 'rank'. For the former, the backend would need to do parallel updates to the DB and the cache. For the latter, if re-sorting on each update is too expensive, something like **Redis** could take care of it for us.

At the **frontend** level: whenever the user goes to the page, the backend sends the full table (or a big chunk of it), not just the first 100 rows (the backend either maintains a cached copy or queries the DB). This approach makes pagination the most responsive, involving no API calls, but it is also the most stale, as the data won't update until the user refreshes the page. In this case, whether the backend maintains a local copy or not only affects the initial load time.

Each approach has its pros and cons. It comes down to the numbers, like the number of rows, the size of each row, the frequency of updates, the duration of a round-trip, how often each feature is used, and so on.

*Did I miss any other options?*

Ultimately, there's no right answer, as it also depends on subjective factors like how much you care about user experience vs data freshness, or how much you care about adding engineering complexity.

The same decision about *where* to do pagination also comes up with row filtering and ordering. It can be done in the DB, backend, or frontend.

For our site, we'll start with the slowest but simplest solution (DB round-trip each time), and we'll optimize as needed.

### Ranking

The 'Ranking' page consists of a set of filters and a table where rows are filtered by those filters.

![Showcase](https://nilmamano.com/blog/wall-game-ui/v07.png)

The mandatory filters are 'Variant' and 'Time control'.

By default, the ranking shows the top 100 players for that variant and time control. We can use pagination to see more.

To fill in each row, we need the following data: rank, player, rating, peak rating, record wins and losses, user creation date, and date of the user's last game.

There is also an optional 'Player' search box. If filled with a player name and the player exists, it jumps directly to the page (100-block) containing that player. If the player does not exist, it shows nothing.

As mentioned, we'll implement pagination and filtering in the DB. We can add a table index on the `display_name` column to speed up the "player search" query:

`display_name`
`CREATE INDEX ON users (display_name);`

Here is the full query:

`-- mandatory filters: :variant, :time_control, :page_number (1-indexed; for pagination)
-- optional: :player_name (if provided, overrides page_number)
WITH ranked AS (
SELECT r.user_id, u.display_name, r.rating, r.peak_rating, r.record_wins,
r.record_losses, u.created_at, r.last_game_at,
-- break ELO ties by oldest account
ROW_NUMBER() OVER (ORDER BY r.rating DESC, u.created_at) AS rank
FROM ratings AS r
JOIN users AS u USING (user_id)
WHERE r.variant = :variant AND r.time_control = :time_control
),
offset_value AS (
SELECT
CASE
WHEN :player_name IS NOT NULL THEN
COALESCE(
(SELECT ((rank - 1) / 100) * 100
FROM ranked
WHERE display_name = :player_name),
0
)
ELSE
(:page_number - 1) * 100
END AS value
)
SELECT * FROM ranked
ORDER BY rank
OFFSET (SELECT value FROM offset_value)
LIMIT 100;`

We include deleted players in the ranking. They'll just show up as something like "Deleted User 23".

### Past games

We already discussed the 'Past games' page in the [Games](#games) section. All the filters have an "all" option which is the default:

We also need pagination: we'll show up to 100 games per page and let the user navigate to the next/previous 100-block.

To fill in each row, we need the following data: variant, rated, time control, board width and height, names and ELOs of all the involved players (could be more than 2 depending on the variant), the number of moves, and the date when the game was played. We also need the game id in case the user wants to watch the game.

`-- mandatory: :page_number (1-indexed; for pagination)
-- optional filters: :variant, :rated, :time_control, :board_size, :min_elo,
-- :max_elo, :date_from, :date_to, :player1, :player2
SELECT g.game_id, g.variant, g.rated, g.time_control, g.board_width,
g.board_height, g.moves_count, g.started_at,
json_agg(
json_build_object(
'player_order', gp.player_order,
-- TODO: check this line
'display_name', COALESCE(u.display_name,
CASE WHEN b.display_name IS NOT NULL
THEN b.display_name
ELSE 'Guest' END),
'rating_at_start', gp.rating_at_start,
'outcome_rank', gp.outcome_rank,
'outcome_reason', gp.outcome_reason
) ORDER BY gp.player_order
) AS players
FROM games AS g
JOIN game_players AS gp USING (game_id)
LEFT JOIN users AS u USING (user_id)
LEFT JOIN built_in_bots AS b USING (bot_id)
WHERE
(:variant IS NULL OR g.variant = :variant)
AND (:rated IS NULL OR g.rated = :rated)
AND (:time_control IS NULL OR g.time_control = :time_control)
AND (
:board_size IS NULL
OR (:board_size = 'small' AND g.board_width * g.board_height <= 36)
OR (:board_size = 'medium' AND g.board_width * g.board_height > 36 AND g.board_width * g.board_height <= 81)
OR (:board_size = 'large' AND g.board_width * g.board_height > 81)
)
AND (:date_from IS NULL OR g.started_at >= :date_from)
AND (:date_to IS NULL OR g.started_at <= :date_to)
AND (
-- Assumes that if :min_elo is NULL, :max_elo is also NULL
:min_elo IS NULL
OR EXISTS (
SELECT 1 FROM game_players AS gp_elo
WHERE gp_elo.game_id = g.game_id
AND gp_elo.rating_at_start IS NOT NULL
AND gp_elo.rating_at_start >= :min_elo
AND (:max_elo IS NULL OR gp_elo.rating_at_start <= :max_elo)
)
)
-- Handle player1 filter
AND (
:player1 IS NULL
OR EXISTS (
SELECT 1 FROM game_players AS gp1
JOIN users AS u1 USING (user_id)
WHERE gp1.game_id = g.game_id
AND u1.display_name = :player1
)
)
-- Handle player2 filter
AND (
:player2 IS NULL
OR EXISTS (
SELECT 1 FROM game_players AS gp2
JOIN users AS u2 USING (user_id)
WHERE gp2.game_id = g.game_id
AND u2.display_name = :player2
)
)
GROUP BY g.game_id
ORDER BY g.started_at DESC
OFFSET (:page_number - 1) * 100
LIMIT 100;`

When the user selects a game to watch, we need to get the moves and configuration parameters, as well as the players' chosen pawn colors and shapes, which we can pull from the `user_settings` table:

`user_settings`
`-- :game_id is the ID of the game to watch
SELECT g.game_id, g.variant, g.time_control, g.rated, g.board_width,
g.board_height, g.started_at, g.views, g.moves_count, gd.config_parameters,
gd.moves,
json_agg(
json_build_object(
'player_order', gp.player_order,
'display_name', COALESCE(u.display_name,
CASE WHEN b.display_name IS NOT NULL
THEN b.display_name
ELSE 'Guest' END),
'rating_at_start', gp.rating_at_start,
'outcome_rank', gp.outcome_rank,
'outcome_reason', gp.outcome_reason,
'pawn_color', COALESCE(us.pawn_color, 'default'),
'pawn_settings', (
SELECT json_object_agg(ups.pawn_type, ups.pawn_shape)
FROM user_pawn_settings AS ups
WHERE ups.user_id = u.user_id
)
) ORDER BY gp.player_order
) AS players
FROM games AS g
JOIN game_details AS gd USING (game_id)
JOIN game_players AS gp USING (game_id)
LEFT JOIN users AS u USING (user_id)
LEFT JOIN built_in_bots AS b USING (bot_id)
LEFT JOIN user_settings AS us ON u.user_id = us.user_id
WHERE g.game_id = :game_id
GROUP BY g.game_id, gd.config_parameters, gd.moves;`

When the user goes to the 'Settings' page, they can change the following settings, and this is stored in the DB:

We pull the settings with this query:

`-- :user_id is the ID of the user whose settings we're retrieving
SELECT
-- General settings
us.dark_theme, us.board_theme, us.pawn_color,
us.default_variant, us.default_time_control, us.default_rated_status,
-- Pawn settings (as JSON array)
(
SELECT json_agg(
json_build_object(
'pawn_type', ups.pawn_type,
'pawn_shape', ups.pawn_shape
)
)
FROM user_pawn_settings AS ups
WHERE ups.user_id = us.user_id
) AS pawn_settings,
-- Variant-specific settings (as JSON array)
(
SELECT json_agg(
json_build_object(
'variant', uvs.variant,
'default_parameters', uvs.default_parameters
)
)
FROM user_variant_settings AS uvs
WHERE uvs.user_id = us.user_id
) AS variant_settings
FROM user_settings AS us
WHERE us.user_id = :user_id;`

To guarantee unique usernames, a user can only change it to a username that does not appear in the DB. We can check this with this query:

`-- :new_display_name is the name the user wants to change to, in lowercase
-- :current_user_id is the ID of the user making the change
SELECT EXISTS(
SELECT 1
FROM users
WHERE display_name = :new_display_name
AND user_id != :current_user_id
) AS name_taken;`

We'd also need queries to update each user settings (changes take effect immediately--there's no final "Update" button in the UI), but these are straightforward.

Finally, if a user chooses to delete their account, we need to rename them to "Deleted User #" where # is the next available number among deleted users, starting from 1. We can do this with this query:

`-- :user_id is the ID of the user to delete
WITH next_deleted_number AS (
SELECT (COUNT(*) + 1) AS num
FROM users
WHERE is_deleted = TRUE
)
UPDATE users
SET
display_name = 'deleted user ' || (SELECT num FROM next_deleted_number),
is_deleted = TRUE,
auth_provider = 'none'
WHERE user_id = :user_id;
-- Also clean up other tables
DELETE FROM user_auth
WHERE user_id = :user_id;
DELETE FROM user_settings
WHERE user_id = :user_id;
DELETE FROM user_pawn_settings
WHERE user_id = :user_id;
DELETE FROM user_variant_settings
WHERE user_id = :user_id;
DELETE FROM user_puzzles
WHERE user_id = :user_id;`

The actual user record remains in the database to maintain game history and statistics, but the user can no longer log in and their personal information is removed.

This concludes the discussion of the DB schema for the Wall Game, a [series](https://nilmamano.com/blog/category/wallgame) of blog posts on building a multiplayer online board game. Next, we'll deep dive into how to train an alpha-zero-like AI for the Wall Game.

## Wall Game UI Design (+ Frontend Generators)

## The Wall Game Project


## Iterative Tree Traversals: A Practical Guide



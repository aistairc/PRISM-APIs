// vim: ts=2 sts=2 sw=2 et ai

"use strict"



const outline = false
const maxThickness = 5

const highlight_color = "blue"
const highlight_color_label = "black"
const highlight_trans = 0.1
const link_text_opacity = 0.5
const nodeSize = 5;

const bow_offset = 20
const default_node_color = "#ccc"
const default_node_label_color = "#000"
const [tocolor, towhite] = outline
  ? ["stroke", "fill"]
  : ["fill", "stroke"]
const regulation_names = {
  "-1": "negative",
  0: "neutral",
  1: "positive",
  2: "mixed",
}
const regMarkers = {
  "-1": "⊖",
  0: "",
  1: "⊕",
  2: "⊙",
}
const regulation_colors = {
  "-1": "#c66",
  0: "#999",
  1: "#6c6",
  2: "#aa6", // mixed
}

const node_colors = {
  Disorder: "#fa0",
}



// Adapted from https://stackoverflow.com/a/43825818/240443
function dist(a, b){
  return Math.sqrt(
    Math.pow(a[0] - b[0], 2) +
    Math.pow(a[1] - b[1], 2))
}
function calcCirclePath(a, b, m) {
  const A = dist(b, m)
  const B = dist(m, a)
  const C = dist(a, b)

  const angle = Math.acos((A*A + B*B - C*C) / (2*A*B))

  //calc radius of circle
  const K = .5*A*B*Math.sin(angle)
  const r = A*B*C/4/K

  //large arc flag
  const laf = +(Math.PI/2 > angle)

  //sweep flag
  const saf = +((b[0] - a[0])*(m[1] - a[1]) - (b[1] - a[1])*(m[0] - a[0]) < 0) 

  return ['M', a, 'A', r, r, 0, laf, saf, b].join(' ')
}

// Adapted from https://math.stackexchange.com/a/995675/145106
function calcBowPath(a, b, o) {
  if (!o) {
    return ['M', a, 'L', b].join(' ')
  } else {
    const dx = b[0] - a[0]
    const dy = b[1] - a[1]
    const s = o / Math.sqrt(dy * dy + dx * dx)
    const m = [
      (a[0] + b[0]) / 2 + s * dy,
      (a[1] + b[1]) / 2 - s * dx,
    ]
    return calcCirclePath(a, b, m)
  }
}
function linkBow(d) {
  if (d.source.x == d.target.x && d.source.y == d.target.y) return ''
  // make sure link fits between the two nodes
  const o = "bidir" in d
    ? (d.bidir - 0.5) * bow_offset
    : 0
  return calcBowPath([d.source.x, d.source.y], [d.target.x, d.target.y], o)
}

let w = window.innerWidth
let h = window.innerHeight

let focus_node = null, highlight_node = null


function tally(items) {
  return items.reduce((a, e) => {
    a[e] ||= 0
    a[e]++
    return a
  }, {})
}
function singleVal(tally, empty, multi) {
  const items = Object.keys(tally)
  if (items.length == 1) {
    return items[0]
  } else if (items.length) {
    return multi
  } else {
    return empty
  }
}
function regulationColor(d) {
  return regulation_colors[d.regulation]
}

function nodeColor(d) {
    return node_colors[d.type] ?? default_node_color
}
function linkLabel(d) {
  let name = d.type
  let reg = d.regulation
  if (reg) {
    name += " " + regMarkers[reg]
  }
  name += ` [${d.id}]` // XXX GTDBEUG
  return name
}



// const simulation = d3.layout.force()
//   .linkDistance(150)
//   .charge(-500)
//   .size([w,h])
// const simulation = d3.forceSimulation()
//   .force("charge", d3.forceManyBody())
//   .force("link", d3.forceLink().distance(150))
//   .force("center", d3.forceCenter(w / 2, h / 2));

const simulation = d3.forceSimulation()
const linkForce =  d3.forceLink()
  .id(d => d.id)
  .distance(100)
const chargeForce = d3.forceManyBody()
const centerForce = d3.forceCenter(w / 2, h / 2)
const collideForce = d3.forceCollide(30)
simulation
  .force("charge", chargeForce)
  .force("center", centerForce)
  .force("link", linkForce)
  .force("collide", collideForce)

setTimeout(() =>
  //simulation.force("collide"
  true,
  500)



const nominal_base_node_size = 5
const nominal_text_size = 10
const nominal_stroke = 0.8
const min_zoom = 0.1
const max_zoom = 10



const svg = d3.select("body").append("svg").style("cursor","move")
const zoom = d3.zoom()
  .scaleExtent([min_zoom, max_zoom])

/* Initialize Group */
const topG = svg.append("g").attr('id', 'top')
const edgeG = topG.append("g").attr('id', 'edges')
const edgeLabelG = topG.append("g").attr('id', 'edge-labels')
const defG = topG.append("g").attr('id', 'defs')
const nodeG = topG.append("g").attr('id', 'nodes')
const nodeLabelG = topG.append("g").attr('id', 'node-labels')

Object.entries(regulation_colors).forEach(([reg, color]) => {
  const regulationName = regulation_names[reg]
  const markerG = defG.append('defs').attr('id', 'defs-' + regulationName)
  for (let i = 1; i <= maxThickness; i++) {
    const t = i + 0.3
    markerG.append('marker')
      .attr('id', 'arrowhead-' + regulationName + "-" + i)
      .attr('class', regulation_names[reg])
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 13)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 13)
      .attr('markerHeight', 13)
      .attr('markerUnits', 'userSpaceOnUse')
      .append('path')
      .attr('d', `M 0,-${t} L 10,0 L 0,${t}`)
      .style('fill', color)
      .style('stroke', 'none')
  }
})

d3.json(graphData).then(graph => {
  graph.nodes.forEach((d, i) => d.id = i)
  graph.links.forEach((d, i) => d.id = i)
  const maxCoEdges = Math.max(...graph.links.map(d => d.instances.length))
  const thicknessScale = maxCoEdges > maxThickness
    ? d3.scale.log().base(2) // XXX scaleSqrt?
      .domain([1, maxCoEdges])
      .range([1, maxThickness])
    : (x => x)
  function getThickness(d) {
    return thicknessScale(d.instances.length)
  }
  function getMarker(d) {
    const regulationName = regulation_names[d.regulation]
    return `url(#arrowhead-${regulationName}-${d.thickness})`
  }

  const linkedByIndex = {}
  graph.links.forEach(d => linkedByIndex[d.source + "," + d.target] = true)
  function isConnected(a, b) {
    return a.index == b.index
      || linkedByIndex[a.index + "," + b.index]
      || linkedByIndex[b.index + "," + a.index]
  }

  simulation.nodes(graph.nodes);
  linkForce.links(graph.links);

  let links = edgeG.selectAll("path")
  let edgelabels = edgeLabelG.selectAll("text")
  let nodes = nodeG.selectAll("circle")
  let nodelabels = nodeLabelG.selectAll("text")

  const drag = d3.drag()
    .on("start", e => {
      if (!e.active) simulation.alphaTarget(0.3).restart()
      e.subject.fx = e.subject.x
      e.subject.fy = e.subject.y
    })
    .on("drag", e => {
      e.subject.fx = e.x
      e.subject.fy = e.y
    })
    .on("end", e => {
      exit_focus()
      if (!e.active) simulation.alphaTarget(0)
      e.subject.fx = null
      e.subject.fy = null
    })

  function update(graph) {
    links = edgeG.selectAll("path")
      .data(graph.links, d => d.id)
    links.exit().remove()
    const linksEnter = links.enter()
      .append("path")
    linksEnter
      .attr('id', d => `edgepath${d.id}`)
      .attr('marker-end', getMarker)
      .style("fill", "none")
    links = links.merge(linksEnter)
    links
      .attr("d", linkBow)
      .style("stroke-width", d => d.thickness)
      .style("stroke", regulationColor)

    edgelabels = edgeLabelG.selectAll("text")
      .data(graph.links, d => d.id)
    edgelabels.exit().remove()
    const edgelabelsEnter = edgelabels.enter()
      .append('text')
      .attr('class', 'edgelabel')
      .attr('font-size', '8')
      .attr('opacity', link_text_opacity)
      //.style("pointer-events", "all")
    edgelabelsEnter
      .append('textPath')
      .attr('xlink:href', d => `#edgepath${d.id}`)
      .style("text-anchor", "middle")
      .style("pointer-events", "all")
      .attr("startOffset", "50%")
    edgelabels = edgelabels.merge(edgelabelsEnter)
      .attr('fill', regulationColor)
      .attr('dy', d => -d.thickness)
      .select('textPath')
      .text(linkLabel)

    nodes = nodeG.selectAll("circle")
      .data(graph.nodes, d => d.id)
    nodes.exit().remove()
    const nodesEnter = nodes.enter()
      .append("circle")
    nodesEnter
      .attr('r', nodeSize)
      .style(tocolor, nodeColor)
      .style("stroke-width", nominal_stroke)
      .style(towhite, "white")
      .on("mouseover", (e, d) => set_highlight(d))
      .on("mouseout", (e, d) => exit_highlight(d))
      .on("mousedown", (e, d) => {
        focus_node = d
        set_focus(d)
        if (!highlight_node) set_highlight(d)
      })
      .style("cursor", "grab")
      .call(drag)
      .append("title")
      .text(d => d.id)
    nodes = nodes.merge(nodesEnter)

    nodelabels = nodeLabelG.selectAll("text")
      .data(graph.nodes, d => d.id)
    nodelabels.exit().remove()
    const nodelabelsEnter = nodelabels.enter()
      .append("text")
    nodelabelsEnter
      .on("mouseover", (e, d) => {
        d3.select(this).style('fill', highlight_color)
      })
      .on("mouseout", (e, d) => {
        d3.select(this).style('fill', default_node_label_color)
      })
      .on("dblclick", (e, d) => {
        d3.select(this).style('fill', default_node_label_color)
        window.open(d.url)
      })
      .attr("dy", ".35em")
      .attr("dx", nodeSize)
      .style("font-size", nominal_text_size + "px")
      .style("cursor", "pointer")
      .style("fill", default_node_label_color)
      .text(d => d.name)
    nodelabels = nodelabels.merge(nodelabelsEnter)

    simulation.nodes(graph.nodes);
    simulation.force("link").links(graph.links);
    simulation.alpha(0.05).restart(); // XXX
  }

  function makeFilter(items, selector, filterCb) {
    const filter = Object.fromEntries(items.map(item => [item, true]))
    const labels = d3.select(selector).selectAll('label').data(items)
    labels.exit().remove()
    const label = labels.enter()
      .append('label')
    const checkbox = label
      .append('input')
      .attr('type', 'checkbox')
      .attr('value', d => d)
      .attr('checked', true)
    label
      .append('span')
      .text(d => ` ${d}`)
    checkbox.on('change', function(e, d) {
      const checked = this.checked;
      filter[d] = checked;
      filterCb()
    })
    return filter
  }

  function makeFilters() {
    const relTypes = [...new Set(graph.links.flatMap(link =>
      link.instances.map(instance => instance.type)
    ))].sort()
    const relFilter = makeFilter(relTypes, '#relation-filters', filter)
    const regTypes = ["Positive", "Negative"]
    const regFilter = makeFilter(regTypes, '#regulation-filters', filter)
    const regTypesRev = Object.fromEntries(regTypes.map((reg, i) => [1 - i * 2, reg]))

    function filter() {
      const links = []
      const seenNodes = new Set()
      graph.links.forEach(link => {
        const newLink = Object.assign({}, link)
        newLink.instances = link.instances.filter(instance =>
          relFilter[instance.type] && regFilter[regTypesRev[instance.regulation]]
        )
        if (newLink.instances.length) {
          links.push(newLink)
          seenNodes.add(link.source.id)
          seenNodes.add(link.target.id)
        }
        const regulations = tally(newLink.instances.map(instance => instance.regulation))
        newLink.regulation = singleVal(regulations, 0, 2)
        const types = tally(newLink.instances.map(instance => instance.type))
        newLink.type = singleVal(types, "", "...")
        newLink.thickness = getThickness(newLink)
      })
      const nodes = graph.nodes.filter(node => seenNodes.has(node.id))
      const newGraph = {
        nodes,
        links,
      }
      update(newGraph)
    }

    return filter
  }

  const filter = makeFilters()
  filter()

  function exit_focus() {
    if (focus_node)  {
      focus_node = null
      if (highlight_trans < 1)  {
        nodes.style("opacity", 1)
        nodelabels.style("opacity", 1)
        links.style("opacity", 1)
        edgelabels.style("opacity", link_text_opacity)
      }
    }

    if (highlight_node) exit_highlight()
  }

  function exit_highlight() {
    highlight_node = null
    if (!focus_node)  {
      svg.style("cursor", "move")
      if (highlight_color != "white") {
        nodes.style(towhite, "white")
        links.style("stroke", regulationColor)
        edgelabels.style("opacity", link_text_opacity)
        // edgelabels.style("fill", regulationColor)
      }
    }
  }

  function set_focus(d)   {
    if (highlight_trans < 1)  {
      nodes.style("opacity", o => isConnected(d, o) ? 1 : highlight_trans)
      nodelabels.style("opacity", o => isConnected(d, o) ? 1 : highlight_trans)
      links.style("opacity", o => o.source.index == d.index || o.target.index == d.index ? 1 : link_text_opacity)
      edgelabels.style("opacity", o => o.source.index == d.index || o.target.index == d.index ? 1 : highlight_trans)
    }
  }

  function set_highlight(d) {
    svg.style("cursor", "pointer")
    if (focus_node) d = focus_node
    highlight_node = d
    if (highlight_color !== "white") {
      nodes.style(towhite, o => isConnected(d, o) ? highlight_color : "white")
      links.style("stroke", o => o.source.index == d.index || o.target.index == d.index ? highlight_color : regulationColor(o))
      edgelabels.style("opacity", o => o.source.index == d.index || o.target.index == d.index ? 1 : highlight_trans)
      // edgelabels.style("fill", o => o.source.index == d.index || o.target.index == d.index ? highlight_color_label : regulationColor(o))
    }
  }

  zoom.on("zoom", e => topG.attr("transform", e.transform))


  svg.call(zoom)
    .on("dblclick.zoom", null)
    .on("mouseup.zoom", null)
  resize()
  window.focus()
  
  simulation.on("tick", tick)
  function tick() {
    const chargeForceStrength = chargeForce.strength()
    if (chargeForceStrength > -500) chargeForce.strength(chargeForceStrength - 1)
    nodes.attr("transform", d => `translate(${d.x.toFixed(4)},${d.y.toFixed(4)})`)
    nodelabels.attr("transform", d => `translate(${d.x.toFixed(4)},${d.y.toFixed(4)})`)
    links.attr("d", linkBow)
  }

  function resize() {
    var width = window.innerWidth, height = window.innerHeight
    svg.attr("width", width).attr("height", height)

    // const simSize = simulation.size()
    // simulation.force("center").initialize(...)? // TODO
    // simulation.size([
    //   simSize[0]+(width-w)/zoom.scale(),
    //   simSize[1]+(height-h)/zoom.scale()],
    // ).resume()
    w = width
    h = height
  }
})

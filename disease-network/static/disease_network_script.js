// vim: ts=2 sts=2 sw=2 et ai

"use strict"



const regNames = {
  "-2": "Unspecified",
  "-1": "Negative",
  0: "Unregulated",
  1: "Positive",
  2: "Mixed",
}
const regColors = {
  "-2": "#aa6",
  "-1": "#c66",
  0: "#000",
  1: "#6c6",
  2: "#660",
}
const nodeColors = {
  "Disorder": "red",
  "GGPs": "purple",
  "Pharmacological_substance": "green",
  "...": "magenta",
  "default": "blue",
}


const minEdgeWidth = 3
const maxEdgeWidth = 10
const logFactor = 2


head.js(
  urls.jquery,
  () => head.js(...urls.libraries, onReady)
)


function debounce(timeout=250, fn) {
  let timer;
  return (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), timeout);
  }
}

function onResize(selector, callback) {
  const resizeObserver = new ResizeObserver(callback)
  $(selector).each(function() {
    resizeObserver.observe(this)
  })
  return resizeObserver
}

function nameComparator(a, b) {
  let aa = a.data('name')
  let bb = b.data('name')
  if (aa.charAt(0) == '"') aa = aa.substring(1, aa.length - 2)
  if (bb.charAt(0) == '"') bb = bb.substring(1, aa.length - 2)
  return aa.localeCompare(bb)
}


let dispatcher
let focus
function onReady() {
  if (!docDataBase) {
    $('#vis').hide()
  }

  Util.loadFonts = function() {};
  window.Configuration = {
    "abbrevsOn": true,
    "textBackgrounds": "striped",
    "visual": {
      "margin": {
        "x": 2,
        "y": 1
      },
      "arcTextMargin": 1,
      "boxSpacing": 1,
      "curlyHeight": 4,
      "arcSpacing": 9,
      "arcStartHeight": 19
    },
    "svgWidth": "100%",
    // "rapidModeOn": false,
    // "confirmModeOn": true,
    // "autorefreshOn": false,
    "typeCollapseLimit": 30
  };
  $('.waiting-ready').prop('disabled', false);
  dispatcher = new Dispatcher();
  const visualizer = new Visualizer(dispatcher, 'brat');
  dispatcher.post('init');
  dispatcher
    .on('doneRendering', onDoneRendering)

  onResize(
    '#vis',
    debounce(
      100,
      evt => dispatcher.post('renderData'),
    ),
  )

  function onDoneRendering() {
    if (focus) {
      let minY = null
      let el
      for (const focusItem of focus) {
        if (focusItem.length == 3) {
          el = $(`[data-arc-origin="${focusItem[0]}"][data-arc-role="${focusItem[1]}"][data-arc-target="${focusItem[2]}"]`)[0]
        } else {
          el = $(`[data-span-id="${focusItem[0]}"]`)[0]
        }
        const y = Math.max(
          el.parentNode.parentNode.parentNode.transform.baseVal[0].matrix.f
          + +el.getAttribute('y') - 20,
          0
        )
        if (!minY || y < minY) {
          minY = y
        }
      }
      $('#vis')[0].scrollTop = minY
    }
  }

  Object.entries(nodeColors).forEach(([type, color]) => {
    $(`#entity-legend [data-type="${type}"]`).css('color', color)
  })
  $('#entity-legend').removeClass('hidden')

  drawGraph(graphData)
}



let cy = null
function drawGraph(graph) {
  cy = cytoscape({
    container: document.getElementById('graph'),
    layout: {
      name: 'fcose',
      quality: 'proof',

    },
    responsive: true,
    elements: {
      nodes: graph.nodes.map(data => ({
        data: {
          ...data,
          id: `n${data.id}`,
        }, 
      })),
      edges: graph.links.map(data => ({
        data: {
          ...data,
          id: `e${data.id}`,
          source: `n${data.source}`,
          target: `n${data.target}`,
        },
      })),
    },
    style: [
      {
        selector: 'node',
        style: {
          'background-color': nodeColors.default,
          'font-size': 7,
          height: 10,
          width: 10,
          label: 'data(name)',
        }
      },
      ...Object.entries(nodeColors).map(([type, color]) => ({
        selector: `node[type="${type}"]`,
        style: {
          'background-color': color,
        }
      })),
      {
        selector: 'edge',
        style: {
          'font-size': 4,
          'text-rotation': 'autorotate',
          'target-arrow-shape': 'triangle',
          'line-opacity': 0.5,
          'curve-style': 'straight',
        }
      },
      {
        selector: 'edge[width]',
        style: {
          width: 'data(width)',
        }
      },
      {
        selector: 'edge[type]',
        style: {
          label: 'data(type)',
        },
      },
      ...Object.entries(regColors).map(([reg, color]) => ({
        selector: `edge[regulation=${reg}]`,
        style: {
          'line-color': color,
          'target-arrow-color': color,
        }
      })),
      {
        selector: '*:selected',
        style: {
          'underlay-color': 'gold',
          'underlay-padding': 5,
          'underlay-shape': 'ellipse',
          'underlay-opacity': 1,
          'z-index': 1001,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'text-outline-color': 'gold',
          'text-outline-width': 2,
        },
      },
      {
        selector: '*.neighborhood',
        style: {
          'underlay-color': 'yellow',
          'underlay-padding': 5,
          'underlay-shape': 'ellipse',
          'underlay-opacity': 1,
          'z-index': 1000,
        },
      },
      {
        selector: 'node.neighborhood',
        style: {
          'text-outline-color': 'yellow',
          'text-outline-width': 1,
        },
      },
    ],
  })
  cy.remove(cy.nodes().filter('[[degree = 0]]'))
  const fullGraphJSON = cy.json()

  // TODO XXX not really working
  let zoomInMargin
  let zoomOutMargin = 10
  function resize() {
    zoomInMargin = Math.min(
      cy.width() / 4,
      cy.height() / 4,
    )
    cy.resize()
  }
  resize = debounce(100, resize)
  onResize('#graph', resize)

  let canZoomIn = false
  let isZoomedIn = false
  function adjustZoomButton() {
    $('#tab-zoom-in-btn').text(canZoomIn && !isZoomedIn ? 'zoom_in' : 'zoom_out')
  }

  cy.on('select', 'node', function(evt) {
    cy.nodes(":selected").neighborhood().addClass('neighborhood')
    displayNodeInfo(this)
    canZoomIn = true
    adjustZoomButton()
  })
  cy.on('select', 'edge', function(evt) {
    cy.edges(":selected").source().addClass('neighborhood')
    cy.edges(":selected").target().addClass('neighborhood')
    displayEdgeInfo(this)
    canZoomIn = true
    adjustZoomButton()
  })
  cy.on('unselect', '*', evt => {
    cy.elements("*.neighborhood").removeClass('neighborhood')
    displayNodeList()
    canZoomIn = false
    adjustZoomButton()
  })
  // TODO on 'position' of '*:selected', isZoomedIn = false
  // however it only works for nodes
  // TODO also, when a different node is selected, isZoomedIn = false
  // however what if the zoomed in node is selected

  cy.on('viewport', evt => {
    if (isZoomedIn) {
      isZoomedIn = false
      adjustZoomButton()
    }
  })
  $('#tab-zoom-in-btn').on('click', e => {
    if (canZoomIn && !isZoomedIn) {
      const selected = cy.elements('*:selected')
      cy.fit(selected, zoomInMargin)
      isZoomedIn = true
      adjustZoomButton()
    } else {
      cy.fit(cy.elements(), zoomOutMargin)
      isZoomedIn = false
      adjustZoomButton()
    }
  })

  // window.cy = cy // DEBUG


  class Filter {
    constructor(items, prop, $element, callback) {
      this.prop = prop
      items = items.map(item => Array.isArray(item) ? item : [item, item])
      this.filter = Object.fromEntries(items.map(([value, name]) => [value, true]))
      this.$counters = []
      for (const [value, name] of items) {
        const $label = $('<label/>')
          .appendTo($element)
        const $cb = $('<input type="checkbox" checked/>')
          .val(value)
          .on('change', evt => {
            this.filter[value] = evt.target.checked
            callback()
          })
          .appendTo($label)
        $('<span/>')
          .text(name + " (")
          .appendTo($label)
        this.$counters[value] = $('<span class="count"/>')
          .appendTo($label)
        $('<span>)</span>')
          .appendTo($label)
      }
    }

    updateCounter(filteredInstances) {
      const counts = {}
      for (const instance of filteredInstances) {
        counts[instance[this.prop]] ??= 0
        counts[instance[this.prop]] += 1
      }
      Object.entries(this.$counters).forEach(([value, $counter]) => {
        $counter.text(counts[value] ?? 0)
      })
    }

    applyTo(instances) {
      return instances.filter(instance => this.filter[instance[this.prop]])
    }

    static updateCounters(filteredInstances, filters) {
      filters.forEach(filter => filter.updateCounter(filteredInstances))
    }

    static applyTo(instances, filters) {
      return filters.reduce(
        (instances, filter) => filter.applyTo(instances),
        instances
      )
    }
  }

  function uniquePropValues(instances, prop) {
    const itemList = instances.map(instance => instance[prop])
    const items = [...new Set(itemList)]
    items.sort()
    return items
  }

  function plural(num) {
    if (Array.isArray(num)) {
      num = num.length
    }
    return num % 10 !== 1 || num % 100 === 11
  }

  const debouncedFiltersChangedHandler = debounce(250, filtersChangedHandler)
  const allEdgeInstances = cy.edges().map(item => item.data('instances')).flat()
  const allNodeInstances = cy.nodes().map(item => item.data('instances')).flat()

  const regFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'regulation').map(reg => [reg, regNames[reg]]),
    'regulation', $('#regulation-filters'), debouncedFiltersChangedHandler
  )
  const eventFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'type'),
    'type', $('#event-filters'), debouncedFiltersChangedHandler
  )
  const entityFilter = new Filter(
    uniquePropValues(allNodeInstances, 'type'),
    'type', $('#entity-filters'), debouncedFiltersChangedHandler
  )
  const docFilter = new Filter(
    uniquePropValues(allEdgeInstances, 'doc'),
    'doc', $('#document-filters'), debouncedFiltersChangedHandler
  )
  const edgeFilters = [regFilter, eventFilter, docFilter]
  const nodeFilters = [entityFilter, docFilter]
  $('#subgraph-filter input').on('input', debouncedFiltersChangedHandler)


  /*
  function singleVal(instances, prop, none, multi) {
    const valList = instances.map(instance => instance[prop])
    const valUniques = [...new Set(valList)]
    if (valUniques.length === 1) {
      return valUniques[0]
    } else {
      return valUniques.length ? multi : none
    }
  }
  */
  function singleVal(instances, prop, none, multi) {
    // pick a max value
    const tally = {}
    let maxVal
    for (const instance of instances) {
      tally[instance[prop]] ??= 0
      tally[instance[prop]]++
      if (tally[instance[prop]] > (tally[maxVal] ?? 0)) {
        maxVal = instance[prop]
      }
    }
    return maxVal ?? none
  }


  function makeDocList() {
    if (!graph["docs"]) {
      $('#tab-docs-btn').hide()
      return
    }
    const docCounts = {}
    for (const doc of Object.keys(graph["docs"])) {
      docCounts[doc] = 0
    }
    cy.edges().each(edge => {
      for (const instance of edge.data("instances")) {
        docCounts[instance["doc"]] += 1
      }
    })
    const $list = $('#doc-list').empty()
    const docs = Object.keys(graph["docs"]).sort()
    for (const doc of docs) {
      const ok = graph["docs"][doc]
      const $docDiv = $('<div/>').appendTo($list)
      $('<span class="link-icon material-symbols-outlined">article</span>').appendTo($docDiv)
      const $doc = $('<span/>')
        .text(doc)
        .appendTo($docDiv)
      if (ok) {
        $doc
          .addClass('link doclink')
          .on('click', evt => displayDoc(doc))
        $('<span/>')
          .text(` (${docCounts[doc]})`)
          .appendTo($docDiv)
      } else {
        $doc.addClass('bad-doc')
      }
    }
  }

  function getDisjointSubgraphs() {
    let subgraphs = {}
    cy.nodes().forEach(node => {
      if (!(node.id() in subgraphs)) {
        const subgraph = []
        cy.elements().dfs({
          roots: [node],
          visit: function(v, e, u, i, d) {
            const id = v.id()
            subgraphs[id] = subgraph
            subgraph.push(id)
          },
          directed: false,
        })
      }
    })
    return subgraphs
  }


  let removedSubgraphs = null;
  let removedNodes = null;
  let removedEdges = null;
  function filtersChangedHandler() {
    if (removedEdges) {
      cy.add(removedSubgraphs)
      cy.add(removedNodes)
      cy.add(removedEdges)
    }
    select(null)

    let maxInstances = 0
    cy.edges().forEach(edge => {
      const edgeData = edge.data()
      edgeData.filteredInstances = Filter.applyTo(edgeData.instances, edgeFilters)
      edgeData.regulation = singleVal(edgeData.filteredInstances, 'regulation', 0, 2)
      edgeData.type = singleVal(edgeData.filteredInstances, 'type', "", "...")
      edgeData.doc = singleVal(edgeData.filteredInstances, 'doc', "", "...")
      const numInstances = edgeData.filteredInstances.length
      if (numInstances > maxInstances) {
        maxInstances = numInstances
      }
      edge.data(edgeData)
    })

    cy.nodes().forEach(node => {
      const nodeData = node.data()
      nodeData.filteredInstances = Filter.applyTo(nodeData.instances, nodeFilters)
      nodeData.doc = singleVal(nodeData.filteredInstances, 'doc', "", "...")
      nodeData.type = singleVal(nodeData.filteredInstances, 'type', "", "...")
      node.data(nodeData)
    })

    // removedEdges = cy.remove(cy.edges().filter(edge => !edge.data('filteredInstances').length))
    removedEdges = cy.remove(cy.edges().filter(edge => !(
      edge.data('filteredInstances').length
      && edge.source().data('filteredInstances').length
      && edge.target().data('filteredInstances').length
    )))
    // removedNodes = cy.remove(cy.nodes().filter('[[degree = 0]]'))
    removedNodes = cy.remove(cy.nodes().filter(node => !(
      node.degree()
      && node.data('filteredInstances').length
    )))

    const subgraphs = getDisjointSubgraphs()
    const minSubgraphSize = +$('#subgraph-filter input').val()
    removedSubgraphs = cy.remove(cy.nodes().filter(node =>
      subgraphs[node.id()].length < minSubgraphSize)
    )

    Filter.updateCounters(
      cy.nodes().map(node => node.data('filteredInstances')).flat(),
      nodeFilters,
    )
    Filter.updateCounters(
      cy.edges().map(edge => edge.data('filteredInstances')).flat(),
      edgeFilters,
    )

    let scale
    if (maxInstances * logFactor <= maxEdgeWidth - minEdgeWidth + 1) {
      scale = x => minEdgeWidth + (x - 1) * logFactor
    } else {
      const log = x => Math.log(x) / Math.log(logFactor)
      const maxLog = log(maxInstances)
      const factor = (maxEdgeWidth - minEdgeWidth) / maxLog
      scale = x => log(x) * factor + minEdgeWidth
    }
    cy.edges().forEach(edge => {
      const width = scale(edge.data('filteredInstances').length)
      edge.data('width', width)
    })

    const nodeList = cy.nodes().sort(nameComparator)
    const $nodeList = $('#node-list').empty()
    $('<h2/>')
      .text('Node List')
      .appendTo($nodeList)
    for (const node of nodeList) {
      const $nodeLink = $('<div/>')
        .appendTo($nodeList)
      $('<span class="link-icon material-symbols-outlined">circle</span>')
        .appendTo($nodeLink)
      $('<span class="link nodelink"/>')
        .text(node.data('name'))
        .on('click', evt => select(node))
        .appendTo($nodeLink)
    }
    makeDocList()
  }
  filtersChangedHandler()


  function select(ele) {
    cy.elements('*:selected').unselect()
    if (ele) {
      ele.select()
    }
  }

  function open3DGraph() {
    const nodeList = cy.nodes()
    const nodeMap = {}
    nodeList.forEach((node, i) => nodeMap[node.id()] = i)
    const nodes = nodeList.map(node => ({
      id: nodeMap[node.id()],
      degree: node.degree(),
      type: node.data('type'),
      name: node.data('name'),
      ...node.position()
    }))
    const edges = cy.edges().map(edge => ({
      source: nodeMap[edge.source().id()],
      target: nodeMap[edge.target().id()],
      size: edge.data('instances').length,
      type: edge.data('type'),
    }))
    const data = { nodes, edges }
    $('#data-for-3d-graph').val(JSON.stringify(data))
    $('#open-3d-graph-form').submit()
  }

  function displayNodeInfo(node) {
    $('#node-list').hide()
    $('#tab-info-cb').prop('checked', true)
    const $info = $('#info').empty()
    const nodeData = node.data()
    $('<h2/>')
      .text('Node Info')
      .appendTo($info)
    $('<h3/>')
      .text(nodeData.name)
      .appendTo($info)

    if (nodeData.cui) {
      const $dbLink = $('<div/>')
        .appendTo($info)
      $('<span class="link-icon material-symbols-outlined">database</span>')
        .appendTo($dbLink)
      $('<a class="dblink link" target="disease-network-cui"></a>')
        .attr('href', nodeData.url)
        .text(nodeData.cui)
        .appendTo($dbLink)
    }

    const types = uniquePropValues(nodeData.filteredInstances, 'type')
    const $typeFs = $('<fieldset/>')
      .appendTo($info)
    $('<legend/>')
      .text(plural(types) ? "Types" : "Type")
      .appendTo($typeFs)
    types.forEach(type => {
      $('<div/>')
        .text(type)
        .appendTo($typeFs)
    })

    ![
      [node.outgoers().edges(), "Influences", "target", "line_end_arrow"],
      [node.incomers().edges(), "Influenced by", "source", "line_start_arrow"],
    ]
      .filter(([item]) => item.length)
      .forEach(([edges, name, otherEnd, icon]) => {
        const $fs = $('<fieldset/>')
          .appendTo($info)
        $('<legend/>')
          .text(name)
          .appendTo($fs)
        edges.forEach(edge => {
          const otherNode = edge[otherEnd].bind(edge)()
          const $docLink = $('<div>')
            .appendTo($fs)
          $('<span class="link-icon material-symbols-outlined"/>')
            .text(icon)
            .appendTo($docLink)
          $('<span class="link edgelink"/>')
            .text(otherNode.data('name'))
            .on('click', evt => select(edge))
            .appendTo($docLink)
        })
      })

    const $docFS = $('<fieldset/>')
      .appendTo($info)
    $('<legend/>')
      .text('Events')
      .appendTo($docFS)
    const $instances = $('<div/>')
      .appendTo($docFS)
    nodeData.filteredInstances.forEach(instance => {
      const $instance = $('<div/>')
        .appendTo($instances)
      $('<span class="link-icon valign-mid material-symbols-outlined">article</span>')
        .appendTo($instance)
      $('<span/>')
        .toggleClass('link doclink', !!docDataBase)
        .text(instance.doc)
        .on('click', evt => displayDoc(instance.doc, instance.brat_ids))
        .appendTo($instance)
      $('<span/>')
        .text(" " + instance.type)
        .appendTo($instance)
    })
  }

  function displayEdgeInfo(edge) {
    $('#node-list').hide()
    $('#tab-info-cb').prop('checked', true)
    const $info = $('#info').empty()
    const edgeData = edge.data()
    const sourceData = edge.source().data()
    const targetData = edge.target().data()


    $('<h2/>')
      .text('Event Info')
      .appendTo($info)
    $('<h3/>')
      .text(edgeData.name)
      .appendTo($info)

    const $sourceLink = $('<div/>')
      .appendTo($info)
    $('<span class="link-icon material-symbols-outlined">circle</span>')
      .appendTo($sourceLink)
    $('<span class="nodelink link"/>')
      .text(edge.source().data().name)
      .on('click', e => select(edge.source()))
      .appendTo($sourceLink)
    $('<div>')
      .text('influences')
      .appendTo($info)
    const $targetLink = $('<div/>')
      .appendTo($info)
    $('<span class="link-icon material-symbols-outlined">circle</span>')
      .appendTo($targetLink)
    $('<span class="nodelink link"/>')
      .text(edge.target().data().name)
      .on('click', e => select(edge.target()))
      .appendTo($targetLink)

    const types = uniquePropValues(edgeData.filteredInstances, 'type')
    const $typeFs = $('<fieldset/>')
      .appendTo($info)
    $('<legend/>')
      .text(plural(types) ? "Types" : "Type")
      .appendTo($typeFs)
    types.forEach(type => {
      $('<div/>')
        .text(type)
        .appendTo($typeFs)
    })

    const classified = Object.fromEntries(
      Object.keys(regNames).map(reg => [reg, []])
    )
    edgeData.filteredInstances.forEach(d => classified[d.regulation].push(d))
    Object.entries(classified)
      .filter(([reg, instances]) => instances.length)
      .forEach(([reg, instances]) => {
        const $fs = $('<fieldset/>')
          .css('border-color', regColors[reg])
          .appendTo($info)
        $('<legend/>')
          .text(regNames[reg])
          .appendTo($fs)
        instances.forEach(instance => {
          const $instance = $('<div/>')
            .appendTo($fs)
          $('<span class="link-icon material-symbols-outlined">article</span>')
            .appendTo($instance)
          $('<span/>')
            .toggleClass('link doclink', !!docDataBase)
            .text(instance.doc)
            .on('click', evt => displayDoc(instance.doc, instance.brat_ids))
            .appendTo($instance)
          $('<span/>')
            .text(' ' + instance.type)
            .appendTo($instance)
        })
      })
  }

  function displayDoc(doc, newFocus) {
    if (!docDataBase) {
      return
    }
    focus = newFocus
    $('#vis').addClass('show')
    fetch(docDataBase + '/' + doc)
    .then(res => res.json())
    .then(currentDocData => {
      if (dispatcher) {
        dispatcher.post('current', [
          null,
          null,
          {
            focus,
          }
        ])
        dispatcher.post('collectionLoaded', [collData])
        dispatcher.post(
          'renderData',
          [currentDocData],
        )
      }
    })
  }

  function displayNodeList() {
    $('#node-list').show()
    $('#info').empty()
  }


  $('#download-json-full').on('click contextmenu', evt => {
    evt.target.href = "data:application/json," + encodeURIComponent(JSON.stringify(fullGraphJSON, null, 2))
  })
  $('#download-json').on('click contextmenu', evt => {
    evt.target.href = "data:application/json," + encodeURIComponent(JSON.stringify(cy.json(), null, 2))
  })
  $('#download-png').on('click contextmenu', evt => {
    evt.target.href = cy.png()
  })
  $('#download-svg').on('click contextmenu', evt => {
    window.b = cy.svg()
    evt.target.href = "data:application/json," + encodeURIComponent(cy.svg())
  })
  $('#open-3d-graph').on('click', open3DGraph)
}

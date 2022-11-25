var w = window.innerWidth;
var h = window.innerHeight;

var focus_node = null, highlight_node = null;

var text_center = false;
var outline = false;

var min_score = 0;
var max_score = 1;

var color = d3.scale.linear()
  .domain([min_score, (min_score+max_score)/2, 10])
  //.range(["gold", "blue", "green", "yellow", "black", "grey", "darkgreen", "pink", "brown", "slateblue", "orange"]);
  .range(["orange", "blue", "green", "yellow", "black", "grey"]);

var highlight_color = "red";
var highlight_color_label = "black";
var highlight_trans = 0.1;

var size = d3.scale.pow().exponent(1)
  .domain([1,100])
  .range([8,24]);


var force = d3.layout.force()
  .linkDistance(150)
  .charge(-300)
  .size([w,h]);


var default_node_color = "#ccc";
//var default_node_color = "rgb(3,190,100)";
var default_positive_color = "#9f9";
var default_negative_color = "#f99";
var default_link_color = "#888";
var nominal_base_node_size = 5;
var nominal_text_size = 10;
var max_text_size = 14;
var nominal_stroke = 0.8;
var max_stroke = 3.5;
var max_base_node_size = 15;
var min_zoom = 0.1;
var max_zoom = 10;
var svg = d3.select("body").append("svg").style("cursor","move");
var zoom = d3.behavior.zoom().scaleExtent([min_zoom,max_zoom])

/* Initialize Group */
var g = svg.append("g").attr("class", "everything");
var marker = g.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '-0 -5 10 10')
        .attr('refX', 13)
        .attr('refY', 0)
        .attr('orient', 'auto')
        .attr('markerWidth', 13)
        .attr('markerHeight', 13)
        .attr('xoverflow', 'visible')
    marker.append('path')
        .attr('d', 'M 0,-1.3 L 10 ,0 L 0,1.3')
        .attr('fill', 'orange')
        //.attr('fill', '#999')
        .style('stroke','none');
//svg.style("cursor","move");

/* Data based on Positive regulation and Regulation Type:: Faster for Debugging */
//d3.json("graph_regulation_url.json", function(error, graph) {
//d3.json("disease_graph_cluster_PRR.json", function(error, graph) {
/* Data based on Positive regulation and Regulation Type With HyperLink */
//d3.json("disease_graph_filter.json", function(error, graph) {
/* Data based on the entire IPF Dataset With HyperLink:: Quite Slow */
//d3.json("disease_graph.json", function(error, graph) {
d3.json(graphData, function(error, graph) {

    var linkedByIndex = {};
        graph.links.forEach(function(d) {
            linkedByIndex[d.source + "," + d.target] = true;
        });
        function isConnected(a, b) {
            return linkedByIndex[a.index + "," + b.index] || linkedByIndex[b.index + "," + a.index] || a.index == b.index;
        }

    force.nodes(graph.nodes)
        .links(graph.links)
        .start();

    var link = g.selectAll(".link")
                .data(graph.links)
                .enter().append("line")
                .attr("class", "link")
                .attr('marker-end','url(#arrowhead)') //The marker-end attribute defines the arrowhead or polymarker that will be drawn at the final vertex of the given shape.
                .style("stroke-width",nominal_stroke)
                .style("stroke", function(d) {
                    if (isNumber(d.type) && d.type>=0) return color(d.type);
                    else return default_link_color;
                })

    /* The <title> element provides an accessible, short-text description of any SVG container element or
        graphics element. Text in a <title> element is not rendered as part of the graphic, but browsers
        usually display it as a tooltip. */
    link.append("title").text(function (d) {return d.label;});

    /* Initialize Edge links */
    var edgepaths = g.selectAll(".edgepath")
            .data(graph.links)
            .enter().append('path')
            .attr('class', 'edgepath')
            .attr('fill-opacity', 0)
            .attr('stroke-opacity', 0)
            .attr('id', function (d, i) {return 'edgepath' + i})
            //.attr('opacity', highlight_trans)
            .style("pointer-events", "all");

    /* Initialize Edge labels */
    var edgelabels = g.selectAll(".edgelabel")
                .data(graph.links)
                .enter().append('text')
                .attr('class', 'edgelabel')
                .attr('id', function (d, i) {return 'edgelabel' + i})
                .attr('font-size', '8')
                //.attr('fill', '#aaa')
                .attr('fill', 'transparent')
                //.attr('opacity', highlight_trans)
                .style("pointer-events", "all");

    edgelabels.append('textPath')
        .attr('xlink:href', function (d, i) {return '#edgepath' + i})
        .style("text-anchor", "middle")
        .style("pointer-events", "all")
        .attr("startOffset", "50%")
        .text(function (d) {return d.label});

    var node = g.selectAll(".node")
                .data(graph.nodes)
                .enter().append("g")
                .attr("class", "node")
                .call(force.drag)
    node.append("title")
        .text(function (d) {return d.id;});

    node.on("dblclick.zoom", function(d) {
        d3.event.stopPropagation();
        var dcx = (window.innerWidth/2-d.x*zoom.scale());
        var dcy = (window.innerHeight/2-d.y*zoom.scale());
        zoom.translate([dcx,dcy]);
        g.attr("transform", "translate("+ dcx + "," + dcy  + ")scale(" + zoom.scale() + ")");
    });

    var tocolor = "fill";
    var towhite = "stroke";
    if (outline) {
        tocolor = "stroke"
        towhite = "fill"
    }

    var circle = node.append("path")
                .attr("d", d3.svg.symbol()
                .size(function(d) { return Math.PI*Math.pow(size(d.type/2)||nominal_base_node_size,2); })
                .type(function(d) { return d.type; }))
                .style(tocolor, function(d) {
                    if (isNumber(d.type) && d.type>=0) return color(d.type);
                    else return default_node_color;
                })
                .style("stroke-width", nominal_stroke)
                .style(towhite, "white");

    var text = g.selectAll(".text")
                .data(graph.nodes)
                .enter().append("text")
                .on("mouseover", function(d, i){
                    d3.select(this) // .text(d.name)
                          .on("click", function() { window.open(d.url); });
                })
                .attr("dy", ".35em")
                .style("font-size", nominal_text_size + "px")
                .style("fill", function(d) {
                  if (d.event_regulation === 1) return "#009900";
                  else if (d.event_regulation === -1) return "#cc0000";
                  else return "#000000";
                })
                //.text(function(d) { return '\u2002' + '\u2002' + d.name; });
                .text(function(d) {
                  let name = d.name;
                  if (d.event_regulation) {
                    name += " " + ((d.event_regulation === 1) ? "⊕" : "⊖");
                  }
                  return '\u2002' + '\u2002' + name;
                });

    node.on("mouseover", function(d) {
        set_highlight(d);
    })
    .on("mousedown", function(d) {
        d3.event.stopPropagation();
        focus_node = d;
        set_focus(d)
        //focus_node = d;
        //set_focus(d)
        if (highlight_node === null) set_highlight(d)
    })
    .on("mouseout", function(d) {
        exit_highlight();
    });

    d3.select(window).on("mouseup", function() {
        if (focus_node!==null)  {
                focus_node = null;
                if (highlight_trans<1)  {
                    circle.style("opacity", 1);
                    text.style("opacity", 1);
                    link.style("opacity", 1);
                    edgelabels.style("opacity", 0);
                }
        }

        if (highlight_node === null) exit_highlight();
    });

    function exit_highlight()   {
        highlight_node = null;
        if (focus_node===null)  {
            svg.style("cursor","move");
            if (highlight_color!="white")   {
                  circle.style(towhite, "white");
                  text.style("font-weight", "normal");
                  link.style("stroke", function(o) {return (isNumber(o.type) && o.type>=0)?color(o.type):default_link_color});
                  edgelabels.style("font-weight", "normal");
            }
        }
    }

    function set_focus(d)   {
        if (highlight_trans<1)  {
            circle.style("opacity", function(o) {
                return isConnected(d, o) ? 1 : highlight_trans;
            });
            text.style("opacity", function(o) {
                return isConnected(d, o) ? 1 : highlight_trans;
            });
            link.style("opacity", function(o) {
                return o.source.index == d.index || o.target.index == d.index ? 1 : highlight_trans;
            });
            edgelabels.style("opacity", function(o) {
                return o.source.index == d.index || o.target.index == d.index ? 1 : highlight_trans;
            });
        }
    }

    function set_highlight(d)   {
        svg.style("cursor","pointer");
        if (focus_node!==null) d = focus_node;
        highlight_node = d;
        if (highlight_color!=="white")   {
            circle.style(towhite, function(o) {
                return isConnected(d, o) ? highlight_color : "white";
            });
            text.style("font-weight", function(o) {
                return isConnected(d, o) ? "bold" : "normal";
            });
            link.style("stroke", function(o) {
              return o.source.index == d.index || o.target.index == d.index ? highlight_color : ((isNumber(o.type) && o.type>=0)?color(o.type):default_link_color);
            });
            edgelabels.style("stroke", function(o) {
            //edgelabels.style("font-weight", function(o) {
              return o.source.index == d.index || o.target.index == d.index ? highlight_color_label : ((isNumber(o.type) && o.type>=0)?color(o.type):default_link_color);
            });
        }
    }

    zoom.on("zoom", function() {
        var stroke = nominal_stroke;
        if (nominal_stroke*zoom.scale()>max_stroke) stroke = max_stroke/zoom.scale();
        link.style("stroke-width",stroke);
        circle.style("stroke-width",stroke);

        var base_radius = nominal_base_node_size;
        if (nominal_base_node_size*zoom.scale()>max_base_node_size) base_radius = max_base_node_size/zoom.scale();
            circle.attr("d", d3.svg.symbol()
            .size(function(d) { return Math.PI*Math.pow(size(d.size)*base_radius/nominal_base_node_size||base_radius,2); })
            .type(function(d) { return d.type; }))

        circle.attr("r", function(d) { return (size(d.size)*base_radius/nominal_base_node_size||base_radius); })
        if (!text_center) text.attr("dx", function(d) { return (size(d.size)*base_radius/nominal_base_node_size||base_radius); });

        var text_size = nominal_text_size;
        if (nominal_text_size*zoom.scale()>max_text_size) text_size = max_text_size/zoom.scale();
        text.style("font-size",text_size + "px");

        g.attr("transform", "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")");
    });

    svg.call(zoom);
    resize();
    window.focus();
    /* //Now we are giving the SVGs co-ordinates - the force layout is generating the co-ordinates which
    this code is using to update the attributes of the SVG elements */
    force.on("tick", function() {
        node.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });
        text.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });
        //link.attr("d", linkArc);

        link.attr("x1", function(d) { return d.source.x; })
          .attr("y1", function(d) { return d.source.y; })
          .attr("x2", function(d) { return d.target.x; })
          .attr("y2", function(d) { return d.target.y; });

        node.attr("cx", function(d) { return d.x; })
          .attr("cy", function(d) { return d.y; });
            edgepaths.attr('d', function (d) {
                return 'M ' + d.source.x + ' ' + d.source.y + ' L ' + d.target.x + ' ' + d.target.y;
            });

            edgelabels.attr('transform', function (d) {
                if (d.target.x < d.source.x) {
                    var bbox = this.getBBox();

                    rx = bbox.x + bbox.width / 2;
                    ry = bbox.y + bbox.height / 2;
                    return 'rotate(180 ' + rx + ' ' + ry + ')';
                }
                else {
                    return 'rotate(0)';
                }
            });
    });

    function resize() {
        var width = window.innerWidth, height = window.innerHeight;
        svg.attr("width", width).attr("height", height);

        force.size([force.size()[0]+(width-w)/zoom.scale(),force.size()[1]+(height-h)/zoom.scale()]).resume();
        w = width;
        h = height;
    }
 });

function isNumber(n) {
  return !isNaN(parseFloat(n)) && isFinite(n);
}

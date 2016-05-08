var identifier_field = 'package';
var blobField = 'content';
var titleField = 'entry';
var bytesField = 'stream_size';
var typeField = 'content_type';
var rows = 20;

function callback(data) {
  var repo_item_access_endpoint = 'http://'+server_ip+':8000/earkweb/earkcore/access_local_repo_item/';

  //var lilyNamespace = 'org.eu.eark';
  
  var results = data.response.numFound;
  var resultMessage = results + ' result';
  if (results != 1)
    resultMessage += 's';
  resultMessage += ' found';
  
  var pages = '';
  if (results > rows) {
    for (p = 1; p <= 20 && (p - 1) * rows < results; p++) {
      var start = (p - 1) * rows;
      if (start == data.response.start)
        pages += p + ' ';
      else
        pages += '<a href="javascript:;" onclick="askSolr(' + start + ')">' + p + '</a> ';
    }
  }
  
  var searchResults = '';
  for (doc of data.response.docs) {
    // strip off extended mime type information string (following ';') if it exists
    var mimeStr = doc[typeField];
    var mime = mimeStr.toString().replace(/;.*/g, '');
    var fileAdress = repo_item_access_endpoint + doc[identifier_field] + "/" + mime + "/" + doc[titleField]; // encodeURIComponent(doc['lily.id']) + '/field/n$' + blobField + '/data?ns.n=' + lilyNamespace;
    var link = '<a href="' + fileAdress + '" target="_blank">' + doc[titleField] + '</a>';
    var bytes = doc[bytesField];
    var filesize;
    if (bytes < 1024)
      filesize = bytes + ' B';
    else if (bytes < 1024 * 1024)
      filesize = Math.floor(bytes / 1024) + ' kB';
    else
      filesize = Math.floor(bytes / (1024 * 1024)) + ' MB';
    searchResults += '<tr><td>' + link + '</td><td>' + filesize + '</td></tr>';
  }
  
  resultMessage = '<div class="results">' + resultMessage + '</div>';
  pages = '<div class="results">' + pages + '</div>';
  
  document.getElementById('output').innerHTML = resultMessage +
      pages + '<table>' + searchResults + '</table>';
}

function askSolr(start) {
  var solrEndpoint = 'http://'+local_solr_server_ip+':8983/solr/earkstorage/';
  window.console.log("solrEndpoint: " + solrEndpoint)
  var queryString = document.forms.find.queryString.value;

  var blobQuery = '';
  if (queryString)
    blobQuery = blobField + ':' + queryString;
  
  var contentTypesQuery = '';
  for (i = 0; i < document.forms.find.contentTypes.options.length; i++) {
    option = document.forms.find.contentTypes.options[i];
    if (option.selected) {
      if (contentTypesQuery) contentTypesQuery += " ";
      contentTypesQuery += typeField + ':' + option.value + '*';
    }
  }

  var package = document.forms.find.package.value;
  var packageQuery = '';
  if (package) {
    packageQuery += identifier_field + ':' + package + '';
  }
  
  var query = '';
  if (blobQuery) query = blobQuery;
  if (packageQuery) {
    if (query)
      query += ' AND ' + packageQuery;
    else
      query = packageQuery;
  }
  if (contentTypesQuery) {
    if (query)
      query += ' AND (' + contentTypesQuery + ')';
    else
      query = contentTypesQuery;
  }
  
  if (!query) query = '*:*';
  
  var sort = document.forms.find.sort.value;
  var sortParameter = '';
  if (sort) {
    sortParameter = '&sort=' + sort;
  }

  window.console.log("query: " + query)
  
  var script = document.createElement('script');
  script.src = solrEndpoint + 'select?q=' + encodeURIComponent(query) +
      sortParameter + '&start=' + start + '&rows=' + rows + '&wt=json&json.wrf=callback';
  document.getElementsByTagName('head')[0].appendChild(script);
}
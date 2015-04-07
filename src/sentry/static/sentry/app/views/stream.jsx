/*** @jsx React.DOM */
var React = require("react");
var Reflux = require("reflux");
var Router = require("react-router");
var $ = require("jquery");

var api = require("../api");
var GroupActions = require("../actions/groupActions");
var GroupListStore = require("../stores/groupStore");
var LoadingError = require("../components/loadingError");
var LoadingIndicator = require("../components/loadingIndicator");
var Pagination = require("../components/pagination");
var RouteMixin = require("../mixins/routeMixin");
var StreamGroup = require('./stream/group');
var StreamActions = require('./stream/actions');
var StreamFilters = require('./stream/filters');
var utils = require("../utils");

var Stream = React.createClass({
  mixins: [
    Reflux.listenTo(GroupListStore, "onAggListChange"),
    RouteMixin,
    Router.Navigation,
    Router.State,
  ],

  propTypes: {
    memberList: React.PropTypes.instanceOf(Array).isRequired,
    setProjectNavSection: React.PropTypes.func.isRequired
  },

  getInitialState() {
    return {
      groupList: [],
      selectAllActive: false,
      multiSelected: false,
      anySelected: false,
      statsPeriod: '24h',
      realtimeActive: true,
      pageLinks: '',
      loading: true,
      error: false
    };
  },

  componentWillMount() {
    this.props.setProjectNavSection('stream');

    this._streamManager = new utils.StreamManager(GroupListStore);
    this._poller = new utils.StreamPoller({
      success: this.onRealtimePoll,
      endpoint: this.getGroupListEndpoint()
    });
    this._poller.enable();

    this.fetchData();
  },

  routeDidChange() {
    this.fetchData();
  },

  componentWillUnmount() {
    this._poller.disable();
  },

  componentDidUpdate(prevProps, prevState) {
    if (prevState.realtimeActive !== this.state.realtimeActive) {
      if (this.state.realtimeActive) {
        this._poller.enable();
      } else {
        this._poller.disable();
      }
    }
  },

  fetchData() {
    GroupListStore.loadInitialData([]);

    this.setState({
      loading: true,
      error: false
    });

    api.request(this.getGroupListEndpoint(), {
      success: (data, _, jqXHR) => {
        this._streamManager.push(data);

        this.setState({
          error: false,
          loading: false,
          pageLinks: jqXHR.getResponseHeader('Link')
        });
      },
      error: () => {
        this.setState({
          error: true,
          loading: false
        });
      },
      complete: () => {
        if (this.state.realtimeActive) {
          this._poller.enable();
        }
      }
    });
  },

  getGroupListEndpoint() {
    var params = this.getParams();
    var queryParams = this.getQuery();
    queryParams.limit = 50;
    var querystring = $.param(queryParams);

    return '/projects/' + params.orgId + '/' + params.projectId + '/groups/?' + querystring;
  },

  handleRealtimeChange(event) {
    this.setState({
      realtimeActive: !this.state.realtimeActive
    });
  },

  handleSelectStatsPeriod(period) {
    this.setState({
      statsPeriod: period
    });
  },

  onRealtimePoll(data) {
    this._streamManager.unshift(data);
  },

  onAggListChange() {
    this.setState({
      groupList: this._streamManager.getAllItems()
    });
  },

  onPage(cursor) {
    var queryParams = this.getQuery();
    queryParams.cursor = cursor;

    this.transitionTo('stream', this.getParams(), queryParams);
  },

  render() {
    var groupNodes = this.state.groupList.map((node) => {
      return <StreamGroup
          key={node.id}
          data={node}
          memberList={this.props.memberList}
          statsPeriod={this.state.statsPeriod} />;
    });

    var params = this.getParams();

    return (
      <div>
        <StreamFilters />
        <div className="group-header-container" data-spy="affix" data-offset-top="134">
          <div className="container">
            <div className="group-header">
              <StreamActions
                orgId={params.orgId}
                projectId={params.projectId}
                onSelectStatsPeriod={this.handleSelectStatsPeriod}
                onRealtimeChange={this.handleRealtimeChange}
                realtimeActive={this.state.realtimeActive}
                statsPeriod={this.state.statsPeriod}
                groupList={this.state.groupList} />
            </div>
          </div>
        </div>
        {this.state.loading ?
          <LoadingIndicator />
        : (this.state.error ?
          <LoadingError onRetry={this.fetchData} />
        :
          <ul className="group-list">
            {groupNodes}
          </ul>
        )}

        <Pagination pageLinks={this.state.pageLinks} onPage={this.onPage} />
      </div>
    );
  }
});

module.exports = Stream;

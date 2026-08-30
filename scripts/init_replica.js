// Reference/manual initialization equivalent to the TA-provided Compose setup.
// The root docker-compose.yml initializes this automatically via mongo-init.
// No member priority is specified, so MongoDB's equal default priority applies.
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" },
    { _id: 2, host: "mongo3:27017" }
  ]
});

package trino

import future.keywords.contains
import future.keywords.in

default allow = false

allow {
	get_users
	input.action.operation in ["ImpersonateUser", "AccessCatalog", "ExecuteQuery"]
}

allow {
	get_current_user_catalogs
}

allow {
	get_catalogs_show_schemas
}

allow {
	get_catalogs_filter_schemas
}

allow {
	get_catalogs_show_tables
}

allow {
	get_filter_tables
}

allow {
	get_select_from_columns
}

allow{
	get_filter_columns
}

get_users {
	names := [name | some obj in data.users; name := obj.user]
	input.context.identity.user in names
}

get_current_user_catalogs {
	user_object := [obj |
		some obj in data.users
		obj.user == input.context.identity.user
	]
	catalogs := [name | some obj in user_object[0].access; name := obj.catalog]

	#print(catalogs)
	input.action.operation == "FilterCatalogs"
	input.action.resource.catalog.name in catalogs
}

get_catalogs_show_schemas {
	user_object := [obj |
		some obj in data.users
		obj.user == input.context.identity.user
	]
	catalogs := [name | some obj in user_object[0].access; name := obj.catalog]

	#print(catalogs)
	input.action.operation == "ShowSchemas"
	input.action.resource.catalog.name in catalogs
}

get_catalogs_filter_schemas {
	user_object := [obj |
		some obj in data.users
		obj.user == input.context.identity.user
	]
	output_array := [
	{"catalog": c, "schema": s} |
		access := user_object[_].access[_] # Iterate over each access block
		c := access.catalog # Extract catalog name
		schema := access.schemas[_] # Iterate over each schema in the catalog
		s := schema.schema # Extract schema name
	]

	#print(output_array)

	input.action.operation == "FilterSchemas"
	item11 := output_array[_] # Iterate through each item in the array
	item11.catalog == input.action.resource.schema.catalogName
	item11.schema == input.action.resource.schema.schemaName
}

get_catalogs_show_tables {
	user_object := [obj |
		some obj in data.users
		obj.user == input.context.identity.user
	]
	output_array := [
	{"catalog": c, "schema": s} |
		access := user_object[_].access[_] # Iterate over each access block
		c := access.catalog # Extract catalog name
		schema := access.schemas[_] # Iterate over each schema in the catalog
		s := schema.schema # Extract schema name
	]

	#print(output_array)

	input.action.operation == "ShowTables"
	item11 := output_array[_] # Iterate through each item in the array
	item11.catalog == input.action.resource.schema.catalogName
	item11.schema == input.action.resource.schema.schemaName
}

get_filter_tables {
	output_array := [
	{"catalog": catalog, "schema": schema, "table": table} |
		user := data.users[_]
		user.user == input.context.identity.user
		access := user.access[_]
		catalog := access.catalog
		schema_entry := access.schemas[_]
		schema := schema_entry.schema
		table_entry := schema_entry.tables[_]
		table := table_entry.table
	]

	input.action.operation == "FilterTables"

	#some item111
	item111 := output_array[_] # Iterate through each item in the array
	item111.catalog == input.action.resource.table.catalogName # Check if the catalog matches
	item111.schema == input.action.resource.table.schemaName # Check if the schema matches
	item111.table == input.action.resource.table.tableName # Check if the table matches
}

get_select_from_columns {
	output_array := [
	{"catalog": catalog, "schema": schema, "table": table} |
		user := data.users[_]
		user.user == input.context.identity.user
		access := user.access[_]
		catalog := access.catalog
		schema_entry := access.schemas[_]
		schema := schema_entry.schema
		table_entry := schema_entry.tables[_]
		table := table_entry.table
	]

	input.action.operation == "SelectFromColumns"

	#some item111
	item111 := output_array[_] # Iterate through each item in the array
	item111.catalog == input.action.resource.table.catalogName # Check if the catalog matches
	item111.schema == input.action.resource.table.schemaName # Check if the schema matches
	item111.table == input.action.resource.table.tableName # Check if the table matches
}

get_filter_columns{
	output_array := [
	{"catalog": catalog, "schema": schema, "table": table} |
		user := data.users[_]
		user.user == input.context.identity.user
		access := user.access[_]
		catalog := access.catalog
		schema_entry := access.schemas[_]
		schema := schema_entry.schema
		table_entry := schema_entry.tables[_]
		table := table_entry.table
	]

	input.action.operation == "FilterColumns"

	#some item111
	item111 := output_array[_] # Iterate through each item in the array
	item111.catalog == input.action.resource.table.catalogName # Check if the catalog matches
	item111.schema == input.action.resource.table.schemaName # Check if the schema matches
	item111.table == input.action.resource.table.tableName # Check if the table matches
}

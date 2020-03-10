SELECT product_location.product_id, product_location.location_id, stock_location.usage
    FROM
         (SELECT move_in.product_id AS product_id, move_in.location_id as location_id
            FROM stock_move_line AS move_in
         UNION
         SELECT  move_out.product_id AS product_id, move_out.location_dest_id as location_id from stock_move_line AS move_out) AS product_location
LEFT JOIN stock_location ON product_location.location_id=stock_location.id
WHERE stock_location.usage in ('internal', 'transit')
ORDER BY product_location.product_id

{
  "description": "Prova pilota: stesso disegno di design.json, 5 istanze per gruppo.",
  "base_seed": 2026,
  "instances_per_group": 5,
  "t_min": 1,
  "t_max": 100,
  "factors": {
    "n": [
      50,
      100
    ],
    "order_strength": [
      0.2,
      0.6
    ],
    "tasks_per_station": [
      3,
      6
    ],
    "time_dist": [
      "uniform"
    ]
  },
  "extra_groups": [
    {
      "n": 50,
      "order_strength": 0.9,
      "tasks_per_station": 3,
      "time_dist": "uniform"
    },
    {
      "n": 100,
      "order_strength": 0.9,
      "tasks_per_station": 3,
      "time_dist": "uniform"
    },
    {
      "n": 50,
      "order_strength": 0.2,
      "tasks_per_station": 3,
      "time_dist": "bimodal"
    },
    {
      "n": 50,
      "order_strength": 0.6,
      "tasks_per_station": 3,
      "time_dist": "bimodal"
    },
    {
      "n": 50,
      "order_strength": 0.2,
      "tasks_per_station": 10,
      "time_dist": "uniform"
    },
    {
      "n": 100,
      "order_strength": 0.2,
      "tasks_per_station": 10,
      "time_dist": "uniform"
    }
  ]
}
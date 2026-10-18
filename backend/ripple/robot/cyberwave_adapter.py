"""Verified digital-twin repositioning, NOT walking or physical locomotion."""

from ripple.robot.base import Pose


class CyberwaveRobotAdapter:
    def __init__(self, client, twin_id, environment_id):
        self.client = client
        self.twin_id = twin_id
        raw = client.twins.get_raw(twin_id)

        def value(key):
            return raw.get(key) if isinstance(raw, dict) else getattr(raw, key, None)

        if str(value("environment_uuid")) != str(environment_id):
            raise ValueError("Twin does not belong to the configured demo environment")
        self.twin = client.twin(twin_id=twin_id)

    def move_to(self, target: Pose):
        self.twin.edit_position(x=target.x, y=target.y, z=0.0)

    def current_pose(self):
        raw = self.client.twins.get_raw(self.twin_id)

        def value(key):
            return raw.get(key) if isinstance(raw, dict) else getattr(raw, key, None)

        x, y = value("position_x"), value("position_y")
        return None if x is None or y is None else Pose(float(x), float(y))

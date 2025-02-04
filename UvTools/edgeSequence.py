import bpy
import bmesh
print("EDGE SEQUENCE IMPORTED")

class EdgeSequence(object):
    def __init__(self, obj: bpy.types.Object):
        '''
        Constructor
        :param obj: The object Mesh whose selected edges are to be sequenced
        '''
        self.obj = obj
        self.inverted = False
        self.bm = None
        self.edges = []
        self.inverted_edges = []
        self.corner_edges = []
        self.uv_layer = None
        self.inner_faces = []
        self.outer_faces = []
        self.active_edge_batch_coords = []
        self.edges_batch_coords = []
        self.inner_faces_batch_coords = []
        self.outer_faces_batch_coords = []
        self.deformed_verts_postion = self.get_deformed_mesh_verts_positions()
        self.parametric_coordinates = []
        self.inner_loops = []
        self.outer_loops = []
        self.is_border = False
        self.inner_uv_coords = []
        self.outer_uv_coords = []
        self.load()

    def load(self):
        '''
        Load the selected edges from the object
        '''

        if self.bm and isinstance(self.bm, bmesh.types.BMesh):
            self.bm.free()

        if self. obj.mode == "EDIT":
            self.bm = bmesh.from_edit_mesh(self.obj.data)
            self.bm.faces.ensure_lookup_table()
            self.bm.edges.ensure_lookup_table()
            self.bm.verts.ensure_lookup_table()
            self.uv_layer = self.bm.loops.layers.uv.active
            self.edges = [e for e in self.bm.edges if e.select]
            self.is_border = any([e.is_boundary for e in self.edges])
            self.get_ordered_edges_sequence()
            self.get_inner_faces()
            self.get_outer_faces()
            if len(self.edges) > 0:
                edges = [self.edges[0]]
                self.active_edge_batch_coords = self.get_edges_batch_coords(edges)
                self.parametric_coordinates = self.get_parametric_coordinates()
            if len(self.edges) > 1:
                edges = self.edges[1:]
                self.edges_batch_coords = self.get_edges_batch_coords(edges)
            if len(self.inner_faces) > 0:
                self.inner_faces_batch_coords = self.get_faces_batch_coords(self.inner_faces)
            if len(self.outer_faces) > 0:
                self.outer_faces_batch_coords = self.get_faces_batch_coords(self.outer_faces)
            if len(self.edges) > 0 and len(self.inner_faces) > 0:
                self.inner_loops = self.get_edges_faces_related_loops(self.edges, self.inner_faces)
                self.inner_uv_coords = self.get_uv_coordinates(self.edges, self.inner_faces, self.uv_layer)
            if len(self.edges) > 0 and len(self.outer_faces) > 0:
                self.outer_loops = self.get_edges_faces_related_loops(self.edges, self.outer_faces)
                self.outer_uv_coords = self.get_uv_coordinates(self.edges, self.outer_faces, self.uv_layer)


    def transfer_uv_coordinates(self, uv_coords):
        '''
        Transfer the UV coordinates to the mesh
        :param uv_coords: The UV coordinates to transfer
        '''
        uv_parametric_coords = self.convert_to_parametric_coordinates(uv_coords)
        transferred_uv_coords = []
        print("Parametric coordinates are: {0}".format(len(self.parametric_coordinates)))
        for co in self.parametric_coordinates:
            for i in range(len(uv_parametric_coords)-1):
                current = uv_parametric_coords[i]
                next = uv_parametric_coords[i + 1]
                if co >= current and co <= next:
                    # find the scale factor
                    scale_factor = (co - current) / (next - current)
                    # find the corresponding UV coordinates
                    vector = (uv_coords[i + 1] - uv_coords[i]) * scale_factor
                    uv = uv_coords[i] + vector
                    transferred_uv_coords.append(uv)
                    break
        # update the UV coordinates
        return transferred_uv_coords

    def set_inner_loops_uv_coordinates(self, uv_coords):
        '''
        Set the UV coordinates of the inner loops
        :param uv_coords: The UV coordinates to set
        '''
        self.set_loops_uv_coordinates(self.inner_loops, uv_coords)

    def set_outer_loops_uv_coordinates(self, uv_coords):
        '''
        Set the UV coordinates of the outer loops
        :param uv_coords: The UV coordinates to set
        '''
        self.set_loops_uv_coordinates(self.outer_loops, uv_coords)


    def set_loops_uv_coordinates(self, loops, uv_coords):
        '''
        Set the UV coordinates of the inner loops
        :param uv_coords: The UV coordinates to set
        '''
        print("Loops:{0}".format(len(loops)))
        print("UV Coords:{0}".format(len(uv_coords)))
        if len(loops) != len(uv_coords):
            print("The number of loops: {0} and UV coordinates {1} do not match".format(len(loops), len(uv_coords)))
            return
        for i in range(len(loops)):
            sub_loops = self.inner_loops[i]
            for loop in sub_loops:
                loop[self.uv_layer].uv = uv_coords[i]
        # update the mesh
        bmesh.update_edit_mesh(self.obj.data)


    def pin_inner_loops(self):
        '''
        Pin the inner loops
        '''
        for loops in self.inner_loops:
            for loop in loops:
                loop[self.uv_layer].pin_uv = True
        # update the mesh
        bmesh.update_edit_mesh(self.obj.data)

    def unpin_inner_loops(self):
        '''
        Unpin the inner loops
        '''
        for loops in self.inner_loops:
            for loop in loops:
                loop[self.uv_layer].pin_uv = False
        # update the mesh
        bmesh.update_edit_mesh(self.obj.data)

    def pin_outer_loops(self):
        '''
        Pin the outer loops
        '''
        for loops in self.outer_loops:
            for loop in loops:
                loop[self.uv_layer].pin_uv = True
        # update the mesh
        bmesh.update_edit_mesh(self.obj.data)


    def unpin_outer_loops(self):
        '''
        Unpin the outer loops
        '''
        for loops in self.outer_loops:
            for loop in loops:
                loop[self.uv_layer].pin_uv = False
        # update the mesh
        bmesh.update_edit_mesh(self.obj.data)

    @property
    def is_mesh_closed_loop(self):
        '''
        Check if the edge sequence is a closed loop
        :return: True if the edge sequence is a closed loop, False otherwise
        '''
        if len(self.edges) < 2:
            return False
        if any(v in self.edges[-1].verts for v in self.edges[0].verts):
            return True
        else:
            return False

    @staticmethod
    def get_uv_coordinates(edges, faces, uv_layer):
        '''
        Get the UV coordinates of the edges filtered by the faces
        :return: The UV coordinates of the edges
        '''
        uv_coords = []
        for i in range(len(edges)):
            previous_edge = edges[i - 1] if i > 0 else None
            edge = edges[i]
            next_edge = edges[i + 1] if i + 1 < len(edges) else None
            verts = [edge.verts[0], edge.verts[1]]
            if next_edge:
                if verts[1] not in next_edge.verts:
                    verts = verts[::-1]
            elif previous_edge:
                if verts[0] not in previous_edge.verts:
                    verts = verts[::-1]
            for vert in verts:
                for loop in vert.link_loops:
                    if loop.face in faces:
                        uv_coords.append(loop[uv_layer].uv)
                        break
        return uv_coords

    def get_edges_faces_related_loops(self, edges, faces):
        '''
        Get the related loops of the edges filtered by the faces
        :return: The related loops of the edges
        '''
        loops = []
        parsed_verts = []
        for i in range(len(edges)):
            previous_edge = edges[i - 1] if i > 0 else None
            edge = edges[i]
            next_edge = edges[i + 1] if i + 1 < len(edges) else None
            verts = [edge.verts[0], edge.verts[1]]
            if next_edge:
                if verts[1] not in next_edge.verts:
                    verts = verts[::-1]
            elif previous_edge:
                if verts[0] not in previous_edge.verts:
                    verts = verts[::-1]
            for vert in verts:
                if vert in parsed_verts:
                    continue
                vert_loops = []
                for loop in vert.link_loops:
                    if loop.face in faces:
                        vert_loops.append(loop)
                parsed_verts.append(vert)
                loops.append(vert_loops)
        return loops


    def get_deformed_mesh_verts_positions(self):
        '''
        Get the deformed mesh vertices positions
        :return: The deformed mesh vertices positions
        '''
        # Get the evaluated object with all deformations applied
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated_obj = self.obj.evaluated_get(depsgraph)

        # Get the final mesh data
        mesh = evaluated_obj.to_mesh()

        # Get the deformed vertex positions
        vertex_positions = [v.co.copy() for v in mesh.vertices]

        # Free the temporary evaluated mesh
        evaluated_obj.to_mesh_clear()

        return vertex_positions

    def get_ordered_edges_sequence(self):
        '''
        Order the edge sequence starting from the active edge
        '''
        active_edge = self.bm.select_history.active
        self.edges = [active_edge]
        next_edge = self.find_next_edge(active_edge)
        # ordering the edges in a sequence
        if next_edge:
            while next_edge:
                self.edges.append(next_edge)
                next_edge = self.find_next_edge(next_edge)
        # let's find the edges to flip and the corner edges
        self.corner_edges = [False] * len(self.edges)
        self.inverted_edges = [False] * len(self.edges)
        for i in range(len(self.edges)):
            current_edge = self.edges[i]
            next_edge = self.edges[i + 1] if i + 1 < len(self.edges) else None
            previous_edge = self.edges[i - 1] if i > 0 else None
            # print("Edge Verts: ({0}, {1})".format(current_edge.verts[0].index, current_edge.verts[1].index))
            if next_edge:
                if any(f in next_edge.link_faces for f in current_edge.link_faces):
                    self.corner_edges[i] = True
                if current_edge.verts[0] in next_edge.verts:
                    self.inverted_edges[i] = True
                    # print("This needs flipping")
            elif previous_edge:
                if current_edge.verts[1] in previous_edge.verts:
                    # print("This needs flipping")
                    self.inverted_edges[i] = True

    def get_edges_batch_coords(self, edges):
        '''
        Get the batch coordinates of the edges
        :return:
        '''
        world_matrix = self.obj.matrix_world
        batch_coords = []
        for edge in edges:
            for vert in edge.verts:
                deformed_vert = self.deformed_verts_postion[vert.index]
                batch_coords.append(world_matrix @ deformed_vert)
        return batch_coords

    def get_faces_batch_coords(self, faces):
        '''
        Get the batch coordinates of the faces
        :param faces: The faces to get the coordinates from
        :return:
        '''
        world_matrix = self.obj.matrix_world
        faces_coords = []
        for face in faces:
            coords = []
            for vert in face.verts:
                deformed_vert = self.deformed_verts_postion[vert.index]
                coords.append(world_matrix @ deformed_vert)
            faces_coords.append(coords)

        return faces_coords

    def get_parametric_coordinates(self):
        '''
        Get the parametric length of the edge sequence
        :return:
        '''
        verts_coords = self.get_edges_verts_coordinates(self.edges)
        return self.convert_to_parametric_coordinates(verts_coords)

    @staticmethod
    def get_edges_verts_coordinates(edges):
        '''
        Get the vectors of the edges
        :return:
        '''
        coordinates = []
        for i in range(len(edges)):
            next_edge = edges[i + 1] if i + 1 < len(edges) else None
            edge = edges[i]
            previous_edge = edges[i - 1] if i > 0 else None
            verts = [edge.verts[0], edge.verts[1]]
            if next_edge:
                if verts[1] not in next_edge.verts:
                    verts = verts[::-1]
            elif previous_edge:
                if verts[0] not in previous_edge.verts:
                    verts = verts[::-1]
            coordinates.append(verts[0].co.copy())
            if i == len(edges) - 1:
                coordinates.append(verts[1].co.copy())
        return coordinates


    @staticmethod
    def convert_to_parametric_coordinates(coordinates):
        """
        Get the parametric coordinates of a list of coordinates
        :return:
        """
        paramentric_coordinates = [0.0]
        total_length = 0.0
        for i in range(1, len(coordinates)):
            previous_coordinates = coordinates[i - 1]
            current_coordinates = coordinates[i]
            vector_length = (current_coordinates - previous_coordinates).length
            paramentric_coordinates.append(total_length + vector_length)
            total_length += vector_length
        return [coord / total_length for coord in paramentric_coordinates]


    def get_inner_faces(self):
        '''
        Get the inner of the edge sequence
        :return:
        '''
        start_loop_idx = 1 if self.inverted else 0
        print("Getting inner face and the loop id is: {0}".format(start_loop_idx))
        self.inner_faces = self.get_border_faces(start_loop_idx)

    def get_outer_faces(self):
        '''
        Get the outer faces of the edge sequence
        :return:
        '''
        print("GETTING OUTER FACES OF THE EDGE SEQUENCE")
        print("The edge sequence is border: {0}".format(self.is_border))
        if self.is_border:
            return []
        start_loop_idx = 0 if self.inverted else 1
        self.outer_faces = self.get_border_faces(start_loop_idx)

    def get_border_faces(self, start_loop_idx=1):
        '''
        Find the faces connected to one side of the edge sequence
        '''
        paresed_faces = []
        for i in range(len(self.edges) - 1):
            next_edge = self.edges[i + 1] if i + 1 < len(self.edges) else None
            current_edge = self.edges[i]
            start_face = current_edge.link_loops[start_loop_idx].face
            if paresed_faces:
                start_face = paresed_faces[-1]
            connected_faces = self.get_faces_between_edges(current_edge, next_edge, start_face)

            for face in connected_faces:
                if face not in paresed_faces:
                    paresed_faces.append(face)
        return paresed_faces

    def find_next_edge(self, edge):
        '''
        Find the next edge in the sequence
        :param edge: The current edge
        :return:
        '''
        selected_edges = list()
        for v in edge.verts:
            for e in v.link_edges:
                # print("   Parsing edge: {0}".format(e.index))
                if e.select and e not in self.edges and e != edge:
                    selected_edges.append(e)

        if len(selected_edges) != 1:
            # print("Could not find the next edge because the length of the array is: {0}".format(len(selected_edges)))
            return None
        return selected_edges[0]

    def get_faces_between_edges(self, first_edge, second_edge, start_face=None):
        '''
        Find the connected faces and orders them based on the drawing order of the faces
        '''
        # print("=====================================")
        start_face_index = start_face.index if start_face else None
        # print("EDGES: ({0}, {1} Start face: {2})".format(first_edge.index, second_edge.index, start_face_index))
        # let's find the shared vertex and the
        connected_faces = []
        is_ordered = first_edge.verts[1] in second_edge.verts
        # print("Is ordered: {0}".format(is_ordered))
        shared_vert = first_edge.verts[is_ordered]
        loop_idx = not is_ordered
        # the link_loops hold the contiguous faces
        # current_face = first_edge.link_loops[loop_idx].face
        #
        # if start_face:
        #     if start_face != current_face:
        #         current_face = first_edge.link_loops[is_ordered].face
        #     if current_face != start_face:
        #         print("**ERROR: Current face {0} does not match the start face: {1}".format(current_face.index,
        #                                                                                     start_face.index))
        current_face = None
        for loop in first_edge.link_loops:

            if loop.face == start_face:
                current_face = loop.face
                break
        if current_face is None:
            return connected_faces
        if second_edge in current_face.edges:
            # print("This is a corner face {0}".format(current_face.index))
            return [current_face]

        connected_faces.append(current_face)
        shared_vert_faces = shared_vert.link_faces
        counter = 0
        while current_face:
            if counter >= 10:
                break
            counter = +1
            face_connected = []
            face_connected = self.get_face_connected_faces(current_face)
            # find the next face
            next_face = None
            for f in face_connected:
                if f not in connected_faces and f in shared_vert_faces and first_edge not in f.edges:
                    next_face = f
                    break

            if next_face:
                connected_faces.append(next_face)
                if second_edge in next_face.edges:
                    # this is the last face
                    current_face = None
                else:
                    current_face = next_face
            else:
                current_face = None

        return connected_faces

    @staticmethod
    def get_face_connected_faces(face):
        connected_faces = []
        for edge in face.edges:
            for link_face in edge.link_faces:
                if link_face in connected_faces or link_face == face:
                    continue
                connected_faces.append(link_face)
        return connected_faces
